# ServerRadar 跨海探测仪表盘 🚀

这是一个轻量级、无侵入、防封堵的云服务器**真实性能探针**系统。
通过中心节点（探针主机）采用纯 SSH 文件推送拉取与底层并发模拟的方法，周期性地检测远端服务器群的**极限磁盘并发能力**与**跨海网络纯净吞吐量**。

---

## 🛠 功能特性
1. **纯净网络测速**：不依赖 `speedtest`（防止测速频繁被 IDC 商家封禁），而是生成实体网络数据包，通过加密通道(`scp`)跨海打向远端并发回传。测出的必定是您两端真实可用的保底带宽。
2. **直击底层 IO**：非表面日志缓存，直接下达绕过页面缓存的 `dd oflag=direct` 压滤指令，每次对拷测试能探明硬盘在并发下的真实底线。
3. **安全与隐私**：
   - 网页端绝不泄露远程主机的真实IP与任何密码特征（采用前端代号隔离）。
   - 被测主机**0环境依赖**，不需要在被监测的机器上安装任何 Agent 或探针（所有的调度全在主探针服务器发起）。
4. **精美数据大屏**：内置 Tailwind CSS 与 ECharts。为了不让跳动的指针糊弄眼睛，最新版已经将图表改换成**详尽的数据账本（分页表格）**，让每一次的周期巡检数据按序保留。

---

## ⚙️ 环境依赖与要求

> **注：此服务仅部署在您的任意一台做为“监控中心”的 Linux 主机上即可，推荐使用 Ubuntu/Debian。**

需要以下底层工具：
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip sshpass
pip3 install flask paramiko psutil
```
*(提示：如遇 `externally-managed-environment` 错误，可添加 `--break-system-packages` 强制安装依赖)*

---

## 🚀 自定义与一键启动

### 第一步：配置您的服务器账本
下载此源码包后，打开 `config.json` 文件进行修改：
```json
{
  "port": 8888, 
  "probe_interval_seconds": 300, 
  "disk_test_size_mb": 500,
  "net_test_size_mb": 5,
  "servers": [
    {
      "id": "server-1",
      "ip": "您的目标服务器IP",
      "port": 22,
      "user": "root",
      "pwd": "您的密码",
      "name": "前台展示名称（如：新加坡主力机）"
    }
  ]
}
```

### 第二步：一键启停系统
在终端中进入该目录，运行控制脚本（程序自带守护进程防掉线）：
```bash
bash control.sh start
```

### 第三步：访问监控大屏
打开您的浏览器，输入：
`http://您探针主机的IP:8888` 
*(请确保云主机的安全组防火墙已放行 8888 端口)*

---

## 🛑 服务控制指令

```bash
bash control.sh start    # 开启或重启监控
bash control.sh stop     # 停止后台监控
bash control.sh restart  # 重启使最新配置生效
bash control.sh logs     # 实时查看节点探针进度与网络异常波动
```
