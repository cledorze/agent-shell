#!/bin/bash

echo "=== Testing Linux Agent System Components Incrementally ==="

# Step 1: Test Python components first
echo "Testing Python components..."
podman compose -f docker-compose.simple.yml build
podman compose -f docker-compose.simple.yml up -d

echo "Waiting 5 seconds for services to start..."
sleep 5

# Check if services are running
echo "Checking knowledge-system..."
if podman exec -it agent_knowledge-system_1 curl -s http://localhost:8085/health > /dev/null; then
    echo "✅ Knowledge System is running"
else
    echo "❌ Knowledge System failed"
fi

echo "Checking agent-system..."
if podman exec -it agent_agent-system_1 curl -s http://localhost:8082/health > /dev/null; then
    echo "✅ Agent System is running"
else
    echo "❌ Agent System failed"
fi

# Stop Python components
podman compose -f docker-compose.simple.yml down

# Step 2: Test VM Manager
echo "Building and testing VM Manager..."
cd vm_manager
podman build -t vm-manager .
podman run -d --name vm-manager-test -p 8083:8083 vm-manager

echo "Waiting 5 seconds for service to start..."
sleep 5

# Check if VM Manager is running
if curl -s http://localhost:8083/health > /dev/null; then
    echo "✅ VM Manager is running"
else
    echo "❌ VM Manager failed"
fi

# Stop VM Manager
podman stop vm-manager-test
podman rm vm-manager-test
cd ..

# Step 3: Test Command Executor
echo "Building and testing Command Executor..."
cd command_executor
podman build -t command-executor .
podman run -d --name command-executor-test -p 8084:8084 command-executor

echo "Waiting 5 seconds for service to start..."
sleep 5

# Check if Command Executor is running
if curl -s http://localhost:8084/health > /dev/null; then
    echo "✅ Command Executor is running"
else
    echo "❌ Command Executor failed"
fi

# Stop Command Executor
podman stop command-executor-test
podman rm command-executor-test
cd ..

echo "Component testing complete."
