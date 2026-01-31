#!/bin/bash

echo "Stopping React frontend..."
kill $(cat frontend.pid) && rm frontend.pid
pkill -f "react-scripts/scripts/start.js --host 0.0.0.0"

sleep 2

echo "All GUI services stopped!"