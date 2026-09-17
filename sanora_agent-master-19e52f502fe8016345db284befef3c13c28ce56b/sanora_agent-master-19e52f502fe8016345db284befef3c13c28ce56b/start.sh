#!/bin/bash

start() {
    echo "启动服务..."
    nohup python run_server.py > server.log 2>&1 &
    echo $! > server.pid
    echo "服务已启动，PID: $(cat server.pid)"
}

stop() {
    echo "停止服务..."
    if [ -f server.pid ]; then
        # 停止所有相关进程
        pkill -f "python run_server.py"
        rm -f server.pid
        echo "服务已停止"
    else
        echo "服务未在运行"
    fi
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) stop; sleep 2; start ;;
    *) echo "用法: $0 {start|stop|restart}" ;;
esac