#!/bin/bash
if [ -f http_server.pid ]; then
    PID=$(cat http_server.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo "HTTP server stopped (PID: $PID)"
        rm http_server.pid
    else
        echo "HTTP server is not running"
        rm http_server.pid
    fi
else
    echo "PID file not found"
fi
