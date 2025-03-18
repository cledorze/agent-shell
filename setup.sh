#!/bin/bash

echo "Setting up Linux Agent System components..."

# Create directory structure
mkdir -p agent_system knowledge_system command_executor/src vm_manager/{cmd/vm_manager,internal/vm} orchestrator/{cmd/orchestrator,internal/service} api_gateway/{cmd/api,internal/handlers}

# Create Dockerfiles for Python components
echo "Creating agent_system Dockerfile..."
cat > agent_system/Dockerfile << 'EOF'
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose the port
EXPOSE 8082

# Run the application
CMD ["python", "main.py"]
EOF

echo "Creating knowledge_system Dockerfile..."
cat > knowledge_system/Dockerfile << 'EOF'
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose the port
EXPOSE 8085

# Run the application
CMD ["python", "main.py"]
EOF

# Create Dockerfile for Rust component
echo "Creating command_executor Dockerfile..."
cat > command_executor/Dockerfile << 'EOF'
FROM rust:1.75.0-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Cargo.toml and Cargo.lock
COPY Cargo.toml ./
# If you have a Cargo.lock file, copy it too
# COPY Cargo.lock ./

# Create placeholder source file to cache dependencies
RUN mkdir -p src && \
    echo "fn main() {println!(\"Hello, World!\");}" > src/main.rs

# Build dependencies
RUN cargo build --release

# Remove the placeholder source
RUN rm -f src/main.rs

# Copy the actual source code
COPY . .

# Build the application
RUN cargo build --release

# Expose the port
EXPOSE 8084

# Run the application
CMD ["./target/release/command_executor"]
EOF

# Create Dockerfiles for Go components
echo "Creating vm_manager Dockerfile..."
cat > vm_manager/Dockerfile << 'EOF'
FROM golang:1.19-bullseye

# Install libvirt development packages
RUN apt-get update && apt-get install -y \
    libvirt-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy go.mod and go.sum files
COPY go.mod ./
COPY go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN go build -o vm_manager ./cmd/vm_manager

# Expose the port
EXPOSE 8083

# Run the application
CMD ["./vm_manager"]
EOF

echo "Creating orchestrator Dockerfile..."
cat > orchestrator/Dockerfile << 'EOF'
FROM golang:1.19-bullseye

WORKDIR /app

# Copy go.mod and go.sum files
COPY go.mod ./
COPY go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN go build -o orchestrator ./cmd/orchestrator

# Expose the port
EXPOSE 8081

# Run the application
CMD ["./orchestrator"]
EOF

echo "Creating api_gateway Dockerfile..."
cat > api_gateway/Dockerfile << 'EOF'
FROM golang:1.19-bullseye

WORKDIR /app

# Copy go.mod and go.sum files
COPY go.mod ./
COPY go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN go build -o api_gateway ./cmd/api

# Expose the port
EXPOSE 8080

# Run the application
CMD ["./api_gateway"]
EOF

# Create requirements.txt files for Python components
echo "Creating Python requirements.txt files..."
cat > agent_system/requirements.txt << 'EOF'
flask==2.3.3
requests==2.31.0
pyyaml==6.0.1
python-dotenv==1.0.0
marshmallow==3.20.1
openai==0.28.0
langchain==0.0.286
transformers==4.32.1
tenacity==8.2.3
EOF

cat > knowledge_system/requirements.txt << 'EOF'
flask==2.3.3
requests==2.31.0
pyyaml==6.0.1
faiss-cpu==1.7.4
sentence-transformers==2.2.2
pymongo==4.5.0
python-dotenv==1.0.0
langchain==0.0.286
EOF

# Create Cargo.toml for Rust component
echo "Creating Rust Cargo.toml..."
cat > command_executor/Cargo.toml << 'EOF'
[package]
name = "command_executor"
version = "0.1.0"
edition = "2021"

[dependencies]
# Using a compatible version of native-tls for Rust 1.75.0
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

# Create Python source files
echo "Creating Python application files..."
cat > agent_system/main.py << 'EOF'
from flask import Flask, request, jsonify
import os
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Get Knowledge System URL from environment variable
KNOWLEDGE_SYSTEM_URL = os.getenv("KNOWLEDGE_SYSTEM_URL", "http://knowledge-system:8085")

@app.route("/process", methods=["POST"])
def process_instruction():
    try:
        data = request.json
        if not data or "instruction" not in data:
            return jsonify({"status": "error", "message": "Instruction is required"}), 400
        
        instruction = data.get("instruction")
        parameters = data.get("parameters", {})
        
        logger.info(f"Processing instruction: {instruction}")
        
        # In a real implementation, this would involve:
        # 1. Natural language understanding to parse the instruction
        # 2. Knowledge retrieval from the knowledge system
        # 3. Generating appropriate commands
        # 4. Executing the commands via command executor or VM manager
        
        # For this minimal implementation, we'll just log the instruction and return a mock response
        response = {
            "status": "success",
            "result": f"Processed instruction: {instruction}",
            "parameters": parameters
        }
        
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error processing instruction: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    logger.info("Starting Agent System on port 8082")
    app.run(host="0.0.0.0", port=8082)
EOF

cat > knowledge_system/main.py << 'EOF'
from flask import Flask, request, jsonify
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize an in-memory knowledge store for demonstration
knowledge_store = {
    "system_commands": {
        "update_system": "sudo zypper up",
        "check_disk_space": "df -h",
        "list_processes": "ps aux",
        "check_memory": "free -h",
        "check_network": "ip addr show"
    },
    "vm_operations": {
        "list_vms": "virsh list --all",
        "start_vm": "virsh start {vm_name}",
        "stop_vm": "virsh shutdown {vm_name}",
        "restart_vm": "virsh reboot {vm_name}",
        "get_vm_info": "virsh dominfo {vm_name}"
    },
    "openSUSE_info": {
        "version": "OpenSUSE Tumbleweed",
        "package_manager": "zypper",
        "kernel": "Rolling release with latest stable kernel"
    }
}

@app.route("/query", methods=["POST"])
def query_knowledge():
    try:
        data = request.json
        if not data or "query" not in data:
            return jsonify({"status": "error", "message": "Query is required"}), 400
        
        query = data.get("query")
        logger.info(f"Knowledge query received: {query}")
        
        # In a real implementation, this would involve:
        # 1. Vector similarity search in an embedded knowledge base
        # 2. Retrieval of relevant documents or knowledge items
        # 3. Ranking and returning the most relevant information
        
        # For this minimal implementation, we'll just do a simple lookup or return mock data
        response = {"status": "success"}
        
        # Simple keyword matching to demonstrate functionality
        if "command" in query or "commands" in query:
            response["result"] = knowledge_store["system_commands"]
        elif "vm" in query or "virtual machine" in query:
            response["result"] = knowledge_store["vm_operations"]
        elif "opensuse" in query.lower() or "suse" in query.lower():
            response["result"] = knowledge_store["openSUSE_info"]
        else:
            response["result"] = f"Knowledge retrieved for query: {query} (mock data)"
        
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error querying knowledge: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    logger.info("Starting Knowledge System on port 8085")
    app.run(host="0.0.0.0", port=8085)
EOF

# Create Rust source files
echo "Creating Rust application files..."
cat > command_executor/src/main.rs << 'EOF'
use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use serde::{Deserialize, Serialize};
use std::process::Command;
use log::{info, error};
use uuid::Uuid;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

// Command request structure
#[derive(Debug, Deserialize)]
struct CommandRequest {
    command: String,
    args: Option<Vec<String>>,
    working_dir: Option<String>,
}

// Command response structure
#[derive(Debug, Serialize)]
struct CommandResponse {
    id: String,
    status: String,
    stdout: String,
    stderr: String,
    exit_code: i32,
}

// In-memory storage for command results
struct AppState {
    command_results: Mutex<HashMap<String, CommandResponse>>,
}

async fn health_check() -> impl Responder {
    HttpResponse::Ok().body("Command Executor service is healthy")
}

async fn execute_command(
    data: web::Data<Arc<AppState>>,
    command_req: web::Json<CommandRequest>,
) -> impl Responder {
    let cmd_id = Uuid::new_v4().to_string();
    
    // Build the command
    let mut cmd = Command::new(&command_req.command);
    
    // Add arguments if provided
    if let Some(args) = &command_req.args {
        cmd.args(args);
    }
    
    // Set working directory if provided
    if let Some(dir) = &command_req.working_dir {
        cmd.current_dir(dir);
    }
    
    info!("Executing command: {:?}", cmd);
    
    // Execute the command
    let output = match cmd.output() {
        Ok(output) => output,
        Err(e) => {
            error!("Failed to execute command: {}", e);
            return HttpResponse::InternalServerError().json(CommandResponse {
                id: cmd_id,
                status: "error".to_string(),
                stdout: "".to_string(),
                stderr: format!("Failed to execute command: {}", e),
                exit_code: -1,
            });
        }
    };
    
    // Convert output to string
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let exit_code = output.status.code().unwrap_or(-1);
    
    let status = if output.status.success() {
        "success"
    } else {
        "failed"
    };
    
    // Create response
    let response = CommandResponse {
        id: cmd_id.clone(),
        status: status.to_string(),
        stdout,
        stderr,
        exit_code,
    };
    
    // Store the result
    data.command_results.lock().unwrap().insert(cmd_id.clone(), response.clone());
    
    HttpResponse::Ok().json(response)
}

async fn get_command_result(
    data: web::Data<Arc<AppState>>,
    path: web::Path<String>,
) -> impl Responder {
    let cmd_id = path.into_inner();
    
    // Get result from storage
    let result = data.command_results.lock().unwrap().get(&cmd_id).cloned();
    
    match result {
        Some(response) => HttpResponse::Ok().json(response),
        None => HttpResponse::NotFound().body(format!("Command result with ID {} not found", cmd_id)),
    }
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    env_logger::init_from_env(env_logger::Env::default().default_filter_or("info"));
    
    let app_data = Arc::new(AppState {
        command_results: Mutex::new(HashMap::new()),
    });
    
    info!("Starting Command Executor service on port 8084");
    
    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(app_data.clone()))
            .route("/health", web::get().to(health_check))
            .route("/execute", web::post().to(execute_command))
            .route("/results/{id}", web::get().to(get_command_result))
    })
    .bind("0.0.0.0:8084")?
    .run()
    .await
}
EOF

# Create Go module files
echo "Creating Go module files..."
# VM Manager
cat > vm_manager/go.mod << 'EOF'
module github.com/yourusername/linux-agent/vm_manager

go 1.19

require (
	github.com/gorilla/mux v1.8.0
	github.com/libvirt/libvirt-go v7.4.0+incompatible
	github.com/sirupsen/logrus v1.9.0
)

require (
	golang.org/x/sys v0.0.0-20220715151400-c0bba94af5f8 // indirect
)
EOF

# Orchestrator
cat > orchestrator/go.mod << 'EOF'
module github.com/yourusername/linux-agent/orchestrator

go 1.19

require (
	github.com/gorilla/mux v1.8.0
	github.com/sirupsen/logrus v1.9.0
)

require (
	golang.org/x/sys v0.0.0-20220715151400-c0bba94af5f8 // indirect
)
EOF

# API Gateway
cat > api_gateway/go.mod << 'EOF'
module github.com/yourusername/linux-agent/api_gateway

go 1.19

require (
	github.com/gorilla/mux v1.8.0
	github.com/sirupsen/logrus v1.9.0
)

require (
	golang.org/x/sys v0.0.0-20220715151400-c0bba94af5f8 // indirect
)
EOF

# Create empty go.sum files for Go components
touch vm_manager/go.sum orchestrator/go.sum api_gateway/go.sum

# Set permissions
chmod -R 755 agent_system knowledge_system command_executor vm_manager orchestrator api_gateway

echo "Setup complete! All components have been configured."
echo "Now you can run 'podman compose build' followed by 'podman compose up -d'"
