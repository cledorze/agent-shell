#!/bin/bash

echo "=== Linux Agent System Build Fix Script ==="
echo "This script will fix the path and build issues with the containers."

# Stop and clean up current containers
echo "Stopping and cleaning up containers..."
podman compose down
podman container prune -f

# Fix Command Executor issues
echo "Fixing Command Executor..."
cd command_executor

# Check if Cargo.toml exists and fix the package name if needed
if [ -f "Cargo.toml" ]; then
    # Ensure package name is correct
    sed -i 's/name = "command-executor"/name = "command_executor"/g' Cargo.toml
    
    # Update Dockerfile CMD to point to the correct binary location
    cat > Dockerfile << 'EOF'
FROM rust:1.75.0-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Cargo.toml and Cargo.lock
COPY Cargo.toml ./
# Copy source code
COPY src ./src

# Build the application
RUN cargo build --release

# Expose the port
EXPOSE 8084

# Run the application
CMD ["./target/release/command_executor"]
EOF
fi

cd ..

# Fix VM Manager issues
echo "Fixing VM Manager..."
cd vm_manager

# Update Dockerfile to ensure binary is in the correct path
cat > Dockerfile << 'EOF'
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
RUN go build -o /app/vm_manager ./cmd/vm_manager

# Expose the port
EXPOSE 8083

# Run the application with absolute path
CMD ["/app/vm_manager"]
EOF

cd ..

# Create a standardized docker-compose.yml file
echo "Creating updated docker-compose.yml..."
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  api-gateway:
    build:
      context: ./api_gateway
      dockerfile: Dockerfile
    image: localhost/linux-agent-api-gateway:local
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
    image: localhost/linux-agent-orchestrator:local  
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
    image: localhost/linux-agent-agent-system:local
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
    image: localhost/linux-agent-vm-manager:local
    ports:
      - "8083:8083"
    volumes:
      - ./vm_manager:/app
    networks:
      - agent-network
    environment:
      - LIBVIRT_CONNECTION=qemu:///system

  command-executor:
    build:
      context: ./command_executor
      dockerfile: Dockerfile
    image: localhost/linux-agent-command-executor:local
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
    image: localhost/linux-agent-knowledge-system:local
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

# Fix command_executor source file if missing
if [ ! -f "command_executor/src/main.rs" ]; then
    echo "Creating command_executor source file..."
    mkdir -p command_executor/src
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
#[derive(Debug, Serialize, Clone)]
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
fi

# Ensure go.mod exists for VM Manager
if [ ! -f "vm_manager/go.mod" ]; then
    echo "Creating VM Manager go.mod..."
    cat > vm_manager/go.mod << 'EOF'
module vm_manager

go 1.19

require (
	github.com/gorilla/mux v1.8.0
	github.com/sirupsen/logrus v1.9.0
)

require golang.org/x/sys v0.0.0-20220715151400-c0bba94af5f8 // indirect
EOF
    touch vm_manager/go.sum
fi

# Ensure main.go exists for VM Manager
if [ ! -f "vm_manager/cmd/vm_manager/main.go" ]; then
    echo "Creating VM Manager main.go..."
    mkdir -p vm_manager/cmd/vm_manager
    cat > vm_manager/cmd/vm_manager/main.go << 'EOF'
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"

	"github.com/gorilla/mux"
	"github.com/sirupsen/logrus"
)

var logger = logrus.New()

// VM represents a virtual machine
type VM struct {
	Name      string   `json:"name"`
	Status    string   `json:"status"`
	IPAddress []string `json:"ipAddress,omitempty"`
}

func main() {
	logger.SetFormatter(&logrus.TextFormatter{
		FullTimestamp: true,
	})
	logger.Info("Starting VM Manager service")

	// Get connection URI from environment
	connURI := os.Getenv("LIBVIRT_CONNECTION")
	if connURI == "" {
		connURI = "qemu:///system"
	}
	logger.Infof("Using libvirt connection: %s", connURI)

	router := mux.NewRouter()
	router.HandleFunc("/vms", listVMsHandler).Methods("GET")
	router.HandleFunc("/vms/{name}", getVMHandler).Methods("GET")
	router.HandleFunc("/vms/{name}/start", startVMHandler).Methods("POST")
	router.HandleFunc("/vms/{name}/stop", stopVMHandler).Methods("POST")
	router.HandleFunc("/vms/{name}/restart", restartVMHandler).Methods("POST")
	router.HandleFunc("/health", healthCheckHandler).Methods("GET")

	port := "8083"
	logger.Infof("VM Manager listening on port %s", port)
	err := http.ListenAndServe(fmt.Sprintf(":%s", port), router)
	if err != nil {
		logger.Fatalf("Failed to start server: %v", err)
	}
}

// Mock handlers (replace with actual libvirt implementation later)
func listVMsHandler(w http.ResponseWriter, r *http.Request) {
	vms := []VM{
		{Name: "openSUSE-1", Status: "running", IPAddress: []string{"192.168.122.100"}},
		{Name: "openSUSE-2", Status: "stopped"},
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(vms)
}

func getVMHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	name := vars["name"]
	
	vm := VM{Name: name, Status: "running", IPAddress: []string{"192.168.122.100"}}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(vm)
}

func startVMHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	name := vars["name"]
	
	logger.Infof("Starting VM: %s", name)
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, "VM %s started successfully", name)
}

func stopVMHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	name := vars["name"]
	
	logger.Infof("Stopping VM: %s", name)
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, "VM %s stopped successfully", name)
}

func restartVMHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	name := vars["name"]
	
	logger.Infof("Restarting VM: %s", name)
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, "VM %s restarted successfully", name)
}

func healthCheckHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("VM Manager service is healthy"))
}
EOF
fi

echo "Fix completed! Now try rebuilding with:"
echo "podman compose build"
echo "podman compose up -d"
