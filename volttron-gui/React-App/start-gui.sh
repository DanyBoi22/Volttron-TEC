#!/bin/bash

# Start React frontend
echo "Starting React frontend..."
npm start -- --host 0.0.0.0 & echo $! > frontend.pid # Starts React app and save its pid
sleep 3

echo "All GUI services started!"