#!/bin/bash

# Start the development server in the background
echo "Starting development server..."
cd /workspaces/mumulib
node esbuild.js --serve &
SERVER_PID=$!

# Wait for server to start
echo "Waiting for server to start..."
sleep 5

# Check if server is running
if curl -s http://localhost:8000 > /dev/null; then
    echo "Server is running on localhost:8000"
    
    # Run the Playwright tests
    echo "Running Playwright tests..."
    npx playwright test
    TEST_EXIT_CODE=$?
    
    # Kill the server
    echo "Stopping server..."
    kill $SERVER_PID
    
    # Exit with the test exit code
    exit $TEST_EXIT_CODE
else
    echo "Server failed to start"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi
