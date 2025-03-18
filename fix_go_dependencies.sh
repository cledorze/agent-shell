#!/bin/bash

echo "Fixing Go dependencies for all components..."

# Fix VM Manager
echo "Fixing VM Manager..."
cd vm_manager

# Download dependencies properly
go get github.com/gorilla/mux
go get github.com/sirupsen/logrus

# Update import paths in all Go files
find . -name "*.go" -type f -exec sed -i 's|github.com/yourusername/linux-agent/vm_manager|vm_manager|g' {} \;
find . -name "*.go" -type f -exec sed -i 's|github.com/user/linux-agent-system/vm-manager|vm_manager|g' {} \;

# Generate correct go.sum
go mod tidy
cd ..

# Fix Orchestrator
echo "Fixing Orchestrator..."
cd orchestrator

# Download dependencies properly
go get github.com/gorilla/mux
go get github.com/sirupsen/logrus

# Update import paths in all Go files
find . -name "*.go" -type f -exec sed -i 's|github.com/yourusername/linux-agent/orchestrator|orchestrator|g' {} \;

# Generate correct go.sum
go mod tidy
cd ..

# Fix API Gateway
echo "Fixing API Gateway..."
cd api_gateway

# Download dependencies properly
go get github.com/gorilla/mux
go get github.com/sirupsen/logrus

# Update import paths in all Go files
find . -name "*.go" -type f -exec sed -i 's|github.com/yourusername/linux-agent/api_gateway|api_gateway|g' {} \;

# Generate correct go.sum
go mod tidy
cd ..

echo "All Go dependencies fixed! Now try running 'podman compose build'"
