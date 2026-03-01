#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PID_FILE="${DIR}/daemon.pid"
LOG_FILE="${DIR}/radar.log"

start() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "⚠️ ServerRadar 已经在运行中! (PID: $(cat $PID_FILE))"
        echo "重启请先执行 ./control.sh stop"
        exit 1
    fi
    echo "==================================="
    echo " 🚀 正在唤醒 ServerRadar 核心阵法..."
    echo "==================================="
    
    # 检查sshpass
    if ! command -v sshpass &> /dev/null; then
        echo "❌ 错误: 未找到 sshpass 命令，请先安装 (apt install sshpass)。"
        exit 1
    fi

    cd "$DIR"
    nohup python3 core.py > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "✅ 守护进程已拉起！PID: $(cat $PID_FILE)"
    echo "📡 请稍等几秒后访问配置中的对应端口 (默认: 8888)"
    echo "🔍 查看日志: ./control.sh logs"
}

stop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 $PID 2>/dev/null; then
            echo "🛑 正在切断探针服务 (PID: $PID)..."
            kill $PID
            rm -f "$PID_FILE"
            echo "✅ 服务已停止。"
        else
            echo "⚠️ PID 文件存在，但进程已不在运行。"
            rm -f "$PID_FILE"
        fi
    else
        echo "⚠️ 未发现正在运行的进程记录。"
    fi
}

logs() {
    tail -f "$LOG_FILE"
}

case "${1:-}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    logs)
        logs
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    *)
        echo "用法: $0 {start|stop|restart|logs}"
        exit 1
esac
