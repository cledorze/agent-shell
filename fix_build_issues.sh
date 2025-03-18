#!/bin/bash

echo "Fixing Linux Agent System build issues..."

# 1. Fix Go dependencies for VM Manager
echo "Fixing VM Manager Go dependencies..."
cd vm_manager
go mod tidy
go get github.com/sirupsen/logrus@v1.9.0
go mod download github.com/sirupsen/logrus
cd ..

# 2. Update native-tls version in Cargo.toml to be compatible with Rust 1.75.0
echo "Fixing Command Executor Rust compatibility..."
cat > command_executor/Cargo.toml << 'EOF'
[package]
name = "command_executor"
version = "0.1.0"
edition = "2021"

[dependencies]
# Downgraded native-tls to be compatible with Rust 1.75.0
native-tls = "0.2.11"
reqwest = { version = "0.11", features = ["json", "blocking"], default-features = false }
tokio = { version = "1", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
actix-web = "4.3.1"
actix-rt = "2.8.0"
env_logger = "0.10.0"
log = "0.4.17"
uuid = { version = "1.3.3", features = ["v4", "serde"] }
futures = "0.3.28"
async-trait = "0.1.68"

[dev-dependencies]
mockito = "1.0.2"
EOF

# 3. Fix permissions for Python applications
echo "Fixing Python application permissions..."
chmod 755 agent_system/main.py knowledge_system/main.py
chmod -R 755 agent_system knowledge_system

# 4. Update docker-compose.yml to use explicit image naming
echo "Updating docker-compose.yml with explicit image naming..."
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  api-gateway:
    build:
      context: ./api_gateway
      dockerfile: Dockerfile
    image: linux-agent-api-gateway:local
    ports:
      - "8080:8080"
    volumes:
      - ./api_gateway:/app
    depends_on:
      - orchestrator
    networks:
      - agent-network
    environment:
      - ORCHESTRATOR_URL=http://orchestrator:8081

  orchestrator:
    build:
      context: ./orchestrator
      dockerfile: Dockerfile
    image: linux-agent-orchestrator:local
    ports:
      - "8081:8081"
    volumes:
      - ./orchestrator:/app
    depends_on:
      - agent-system
      - vm-manager
      - command-executor
    networks:
      - agent-network
    environment:
      - AGENT_SYSTEM_URL=http://agent-system:8082
      - VM_MANAGER_URL=http://vm-manager:8083
      - COMMAND_EXECUTOR_URL=http://command-executor:8084

  agent-system:
    build:
      context: ./agent_system
      dockerfile: Dockerfile
    image: linux-agent-agent-system:local
    ports:
      - "8082:8082"
    volumes:
      - ./agent_system:/app:Z
    depends_on:
      - knowledge-system
    networks:
      - agent-network
    environment:
      - KNOWLEDGE_SYSTEM_URL=http://knowledge-system:8085

  vm-manager:
    build:
      context: ./vm_manager
      dockerfile: Dockerfile
    image: linux-agent-vm-manager:local
    ports:
      - "8083:8083"
    volumes:
      - ./vm_manager:/app
      - /var/run/libvirt/libvirt-sock:/var/run/libvirt/libvirt-sock
    privileged: true
    networks:
      - agent-network
    environment:
      - LIBVIRT_CONNECTION=qemu:///system

  command-executor:
    build:
      context: ./command_executor
      dockerfile: Dockerfile
    image: linux-agent-command-executor:local
    ports:
      - "8084:8084"
    volumes:
      - ./command_executor:/app
    networks:
      - agent-network

  knowledge-system:
    build:
      context: ./knowledge_system
      dockerfile: Dockerfile
    image: linux-agent-knowledge-system:local
    ports:
      - "8085:8085"
    volumes:
      - ./knowledge_system:/app:Z
    networks:
      - agent-network

networks:
  agent-network:
    driver: bridge
EOF

# 5. Clean previous build artifacts and containers
echo "Cleaning previous build artifacts and containers..."
podman compose down
podman container prune -f
podman image prune -f

echo "Fix complete. Now try running 'podman compose build' and 'podman compose up -d'"
