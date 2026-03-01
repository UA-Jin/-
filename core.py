import json
import os
import re
import socket
import subprocess
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, send_file
import paramiko

# ---------------- 配置加载 ----------------
BASE_DIR = Path(__file__).resolve().parent
CFG_FILE = BASE_DIR / "config.json"
HTML_FILE = BASE_DIR / "index.html"

try:
    with open(CFG_FILE, 'r', encoding='utf-8') as f:
        CONF = json.load(f)
except Exception as e:
    print(f"配置文件 config.json 读取失败: {e}")
    exit(1)

SERVERS = CONF.get("servers", [])
PORT = CONF.get("port", 8888)
INTERVAL = CONF.get("probe_interval_seconds", 300)
DISK_MB = CONF.get("disk_test_size_mb", 500)
NET_MB = CONF.get("net_test_size_mb", 5)

# ---------------- 全局状态池 ----------------
app = Flask(__name__)

state = { s['id']: {"disk_write": 0, "disk_read": 0, "net_in": 0, "net_out": 0, "time": 0} for s in SERVERS }
history = { s['id']: [] for s in SERVERS }

# ---------------- 核心嗅探器 ----------------

def ensure_dummy_file():
    # 本地生成网络包裹
    target_file = f"/tmp/radar_{NET_MB}m.bin"
    if not os.path.exists(target_file):
        subprocess.run(f"dd if=/dev/zero of={target_file} bs=1M count={NET_MB} 2>/dev/null", shell=True)
    return target_file

def _get_disk_speed(ssh, sid):
    # 下发读写命令 (直击底层)
    cmd_disk = f"""
    w_res=$(dd if=/dev/zero of=/tmp/radar_speed bs={DISK_MB}M count=1 oflag=direct 2>&1 | tail -n 1 | awk -F'，' '{{print $NF}}')
    r_res=$(dd if=/tmp/radar_speed of=/dev/null bs={DISK_MB}M count=1 iflag=direct 2>&1 | tail -n 1 | awk -F'，' '{{print $NF}}')
    rm -f /tmp/radar_speed
    echo "DISK|${{w_res}}|${{r_res}}"
    """
    
    r_bps, w_bps = 0, 0
    try:
        _, stdout, _ = ssh.exec_command(cmd_disk)
        output = stdout.read().decode('utf-8').strip().split('\n')
        for line in output:
            if line.startswith("DISK|"):
                parts = line.split('|')
                def parse_speed(s):
                    if not s.strip(): return 0
                    m = re.search(r'([0-9.]+)\s*([a-zA-Z]+/s)', s)
                    if not m: return 0
                    val = float(m.group(1))
                    unit = m.group(2).upper()
                    if 'GB' in unit: val *= 1024*1024*1024
                    elif 'MB' in unit: val *= 1024*1024
                    elif 'KB' in unit: val *= 1024
                    return val
                w_bps = parse_speed(parts[1])
                r_bps = parse_speed(parts[2])
    except Exception as e:
        print(f"[{sid}] 盘测异常: {e}")
        
    return r_bps, w_bps

def _run_network_test(srv):
    sid = srv['id']
    ip = srv['ip']
    pwd = srv['pwd']
    port = srv.get('port', 22)
    user = srv.get('user', 'root')
    
    local_file = ensure_dummy_file()
    remote_file = f"/tmp/radar_net_test_{sid}.bin"
    down_file = f"/tmp/radar_net_down_{sid}.bin"
    
    net_in_bps, net_out_bps = 0, 0
    timeout_sec = 240 # 最大容忍4分钟
    
    try:
        # 上推 (测试 VPS网入)
        t1 = time.time()
        r1 = subprocess.run(f"sshpass -p '{pwd}' scp -o StrictHostKeyChecking=no -P {port} {local_file} {user}@{ip}:{remote_file}", shell=True, capture_output=True, timeout=timeout_sec)
        t2 = time.time()
        if r1.returncode == 0 and (t2 - t1) > 0:
            net_in_bps = (NET_MB * 1024 * 1024) / (t2 - t1)
            
        # 回拉 (测试 VPS网出)
        t3 = time.time()
        r2 = subprocess.run(f"sshpass -p '{pwd}' scp -o StrictHostKeyChecking=no -P {port} {user}@{ip}:{remote_file} {down_file}", shell=True, capture_output=True, timeout=timeout_sec)
        t4 = time.time()
        if r2.returncode == 0 and (t4 - t3) > 0:
            net_out_bps = (NET_MB * 1024 * 1024) / (t4 - t3)
            
        # 清扫
        subprocess.run(f"sshpass -p '{pwd}' ssh -o StrictHostKeyChecking=no -p {port} {user}@{ip} 'rm -f {remote_file}'", shell=True)
        subprocess.run(f"rm -f {down_file}", shell=True)
    except Exception as e:
        print(f"[{sid}] 网测异常: {e}")
        
    return net_in_bps, net_out_bps

def probe_worker(srv):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    sid = srv['id']
    ip = srv['ip']
    
    while True:
        try:
            print(f"[{sid}] 启动本轮巡航...")
            ssh.connect(ip, port=srv.get('port', 22), username=srv.get('user', 'root'), password=srv['pwd'], timeout=10)
            dr, dw = _get_disk_speed(ssh, sid)
            ni, no = _run_network_test(srv)
            
            ts = int(time.time())
            record = { "time": ts, "disk_read": dr, "disk_write": dw, "net_in": ni, "net_out": no }
            state[sid] = record
            history[sid].insert(0, record)
            
            # 保留约 1 天的记录总量 (假如5分钟跑一次，288次)
            if len(history[sid]) > 300:
                history[sid].pop()
                
            ssh.close()
            print(f"[{sid}] 探测完毕，进入休眠 ({INTERVAL}s)。")
        except Exception as e:
            print(f"[{sid}] 连接闪断或遭遇阻击: {e}")
        
        # 安全休眠
        time.sleep(INTERVAL)

# ---------------- Web 服务路由 ----------------

@app.route('/')
def route_index():
    return send_file(HTML_FILE)

@app.route('/api/stats')
def route_stats():
    # 数据脱敏，不输出 IP, USER, PWD 给前端
    clean_meta = [{"id": s['id'], "name": s['name']} for s in SERVERS]
    return jsonify({
        "servers": clean_meta,
        "history": history,
        "current": state
    })

if __name__ == '__main__':
    for srv in SERVERS:
        t = threading.Thread(target=probe_worker, args=(srv,), daemon=True)
        t.start()
    app.run(host='0.0.0.0', port=PORT)

