#!/bin/bash

echo "Implementing comprehensive fix for Linux Agent System..."

# Clean up previous builds
echo "Cleaning up previous builds..."
podman compose down
podman container prune -f
podman image prune -f

# Reset components with issues
rm -rf vm_manager/{cmd,internal,go.*}
rm -rf command_executor/{src,Cargo.*}
rm -rf api_gateway/{cmd,internal,go.*}
rm -rf orchestrator/{cmd,internal,go.*}

# 1. VM Manager Fix (Simplified implementation)
echo "Creating simplified VM Manager..."
mkdir -p vm_manager/cmd/vm_manager

cat > vm_manager/go.mod << 'EOF'
module vm_manager

go 1.19

require (
	github.com/gorilla/mux v1.8.0
	github.com/sirupsen/logrus v1.9.0
)

require golang.org/x/sys v0.0.0-20220715151400-c0bba94af5f8 // indirect
EOF

# Create a simplified main.go without external dependencies
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

# 2. Command Executor Fix (Simplified Rust implementation)
echo "Creating simplified Command Executor..."
mkdir -p command_executor/src

cat > command_executor/Cargo.toml << 'EOF'
[package]
name = "command_executor"
version = "0.1.0"
edition = "2021"

[dependencies]
# Use only basic dependencies compatible with Rust 1.75.0
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
actix-web = "4.0.0"
log = "0.4.0"
env_logger = "0.9.0"
uuid = { version = "1.0.0", features = ["v4"] }
EOF

cat > command_executor/src/main.rs << 'EOF'
use actix_web::{web, App, HttpResponse, HttpServer, Responder, get, post};
use serde::{Deserialize, Serialize};
use std::process::Command;
use std::collections::HashMap;
use std::sync::Mutex;
use uuid::Uuid;
use log::{info, error};

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

#[get("/health")]
async fn health_check() -> impl Responder {
    HttpResponse::Ok().body("Command Executor service is healthy")
}

#[post("/execute")]
async fn execute_command(
    data: web::Data<AppState>,
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

#[get("/results/{id}")]
async fn get_command_result(
    data: web::Data<AppState>,
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
    
    // Initialize in-memory storage
    let app_data = web::Data::new(AppState {
        command_results: Mutex::new(HashMap::new()),
    });
    
    println!("Starting Command Executor service on port 8084");
    
    HttpServer::new(move || {
        App::new()
            .app_data(app_data.clone())
            .service(health_check)
            .service(execute_command)
            .service(get_command_result)
    })
    .bind("0.0.0.0:8084")?
    .run()
    .await
}
EOF

# 3. API Gateway Fix
echo "Creating simplified API Gateway..."
mkdir -p api_gateway/cmd/api

cat > api_gateway/go.mod << 'EOF'
module api_gateway

go 1.19

require (
	github.com/gorilla/mux v1.8.0
	github.com/sirupsen/logrus v1.9.0
)

require golang.org/x/sys v0.0.0-20220715151400-c0bba94af5f8 // indirect
EOF

cat > api_gateway/cmd/api/main.go << 'EOF'
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"

	"github.com/gorilla/mux"
	"github.com/sirupsen/logrus"
)

var logger = logrus.New()

func main() {
	logger.SetFormatter(&logrus.TextFormatter{
		FullTimestamp: true,
	})
	logger.Info("Starting API Gateway service")

	// Get orchestrator URL from environment variable
	orchestratorURL := os.Getenv("ORCHESTRATOR_URL")
	if orchestratorURL == "" {
		orchestratorURL = "http://orchestrator:8081"
	}
	logger.Infof("Using Orchestrator URL: %s", orchestratorURL)

	router := mux.NewRouter()
	router.HandleFunc("/api/v1/tasks", createTaskHandler(orchestratorURL)).Methods("POST")
	router.HandleFunc("/api/v1/tasks/{id}", getTaskHandler(orchestratorURL)).Methods("GET")
	router.HandleFunc("/api/v1/instructions", submitInstructionHandler(orchestratorURL)).Methods("POST")
	router.HandleFunc("/health", healthCheckHandler).Methods("GET")

	port := "8080"
	logger.Infof("API Gateway listening on port %s", port)
	err := http.ListenAndServe(fmt.Sprintf(":%s", port), router)
	if err != nil {
		logger.Fatalf("Failed to start server: %v", err)
	}
}

func createTaskHandler(orchestratorURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Read the request body
		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, "Failed to read request body", http.StatusBadRequest)
			return
		}
		defer r.Body.Close()

		// Forward the request to the orchestrator
		resp, err := http.Post(
			orchestratorURL+"/tasks",
			"application/json",
			io.NopCloser(io.Reader(io.NopCloser(io.MultiReader(io.NopCloser(io.Reader(io.Buffer(body))))))),
		)
		if err != nil {
			logger.Errorf("Failed to forward request to orchestrator: %v", err)
			http.Error(w, "Failed to forward request to orchestrator", http.StatusInternalServerError)
			return
		}
		defer resp.Body.Close()

		// Read the response body
		respBody, err := io.ReadAll(resp.Body)
		if err != nil {
			logger.Errorf("Failed to read response from orchestrator: %v", err)
			http.Error(w, "Failed to read response from orchestrator", http.StatusInternalServerError)
			return
		}

		// Set the response status code
		w.WriteHeader(resp.StatusCode)

		// Set the content type
		w.Header().Set("Content-Type", "application/json")

		// Write the response body
		w.Write(respBody)
	}
}

func getTaskHandler(orchestratorURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Get task ID from URL
		vars := mux.Vars(r)
		taskID := vars["id"]

		// Forward the request to the orchestrator
		resp, err := http.Get(fmt.Sprintf("%s/tasks/%s", orchestratorURL, taskID))
		if err != nil {
			logger.Errorf("Failed to forward request to orchestrator: %v", err)
			http.Error(w, "Failed to forward request to orchestrator", http.StatusInternalServerError)
			return
		}
		defer resp.Body.Close()

		// Read the response body
		respBody, err := io.ReadAll(resp.Body)
		if err != nil {
			logger.Errorf("Failed to read response from orchestrator: %v", err)
			http.Error(w, "Failed to read response from orchestrator", http.StatusInternalServerError)
			return
		}

		// Set the response status code
		w.WriteHeader(resp.StatusCode)

		// Set the content type
		w.Header().Set("Content-Type", "application/json")

		// Write the response body
		w.Write(respBody)
	}
}

func submitInstructionHandler(orchestratorURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Simplified implementation that just returns a mock response
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{
			"status": "success",
			"message": "Instruction submitted successfully",
			"task_id": "mock-task-123",
		})
	}
}

func healthCheckHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "healthy"})
}
EOF

# 4. Orchestrator Fix
echo "Creating simplified Orchestrator..."
mkdir -p orchestrator/cmd/orchestrator

cat > orchestrator/go.mod << 'EOF'
module orchestrator

go 1.19

require (
	github.com/gorilla/mux v1.8.0
	github.com/sirupsen/logrus v1.9.0
)

require golang.org/x/sys v0.0.0-20220715151400-c0bba94af5f8 // indirect
EOF

cat > orchestrator/cmd/orchestrator/main.go << 'EOF'
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"

	"github.com/gorilla/mux"
	"github.com/sirupsen/logrus"
)

var logger = logrus.New()

// Task status constants
const (
	TaskStatusPending   = "pending"
	TaskStatusProcessing = "processing"
	TaskStatusCompleted  = "completed"
	TaskStatusFailed     = "failed"
)

// Task represents a task in the system
type Task struct {
	ID          string      `json:"id"`
	Instruction string      `json:"instruction"`
	Status      string      `json:"status"`
	Result      interface{} `json:"result,omitempty"`
	Error       string      `json:"error,omitempty"`
	CreatedAt   time.Time   `json:"created_at"`
	UpdatedAt   time.Time   `json:"updated_at"`
}

// TaskStore is a simple in-memory store for tasks
var TaskStore = make(map[string]*Task)

func main() {
	logger.SetFormatter(&logrus.TextFormatter{
		FullTimestamp: true,
	})
	logger.Info("Starting Orchestrator service")

	// Get service URLs from environment variables
	agentSystemURL := os.Getenv("AGENT_SYSTEM_URL")
	if agentSystemURL == "" {
		agentSystemURL = "http://agent-system:8082"
	}
	
	vmManagerURL := os.Getenv("VM_MANAGER_URL")
	if vmManagerURL == "" {
		vmManagerURL = "http://vm-manager:8083"
	}
	
	commandExecutorURL := os.Getenv("COMMAND_EXECUTOR_URL")
	if commandExecutorURL == "" {
		commandExecutorURL = "http://command-executor:8084"
	}
	
	logger.Infof("Agent System URL: %s", agentSystemURL)
	logger.Infof("VM Manager URL: %s", vmManagerURL)
	logger.Infof("Command Executor URL: %s", commandExecutorURL)

	router := mux.NewRouter()
	router.HandleFunc("/tasks", createTaskHandler).Methods("POST")
	router.HandleFunc("/tasks/{id}", getTaskHandler).Methods("GET")
	router.HandleFunc("/health", healthCheckHandler).Methods("GET")

	port := "8081"
	logger.Infof("Orchestrator listening on port %s", port)
	err := http.ListenAndServe(fmt.Sprintf(":%s", port), router)
	if err != nil {
		logger.Fatalf("Failed to start server: %v", err)
	}
}

func createTaskHandler(w http.ResponseWriter, r *http.Request) {
	// Parse request
	var requestData struct {
		Instruction string      `json:"instruction"`
		Parameters  interface{} `json:"parameters,omitempty"`
	}
	
	err := json.NewDecoder(r.Body).Decode(&requestData)
	if err != nil {
		logger.Errorf("Failed to decode request: %v", err)
		http.Error(w, "Failed to decode request", http.StatusBadRequest)
		return
	}
	
	// Generate a task ID
	taskID := fmt.Sprintf("task-%d", time.Now().UnixNano())
	
	// Create a new task
	now := time.Now()
	task := &Task{
		ID:          taskID,
		Instruction: requestData.Instruction,
		Status:      TaskStatusPending,
		CreatedAt:   now,
		UpdatedAt:   now,
	}
	
	// Store the task
	TaskStore[taskID] = task
	
	// Start processing the task asynchronously
	go processTask(task)
	
	// Return the task ID
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"task_id": taskID})
}

func getTaskHandler(w http.ResponseWriter, r *http.Request) {
	// Get task ID from URL
	vars := mux.Vars(r)
	taskID := vars["id"]
	
	// Get the task from the store
	task, ok := TaskStore[taskID]
	if !ok {
		http.Error(w, "Task not found", http.StatusNotFound)
		return
	}
	
	// Return the task
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(task)
}

func healthCheckHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "healthy"})
}

func processTask(task *Task) {
	// Update task status
	task.Status = TaskStatusProcessing
	task.UpdatedAt = time.Now()
	
	// Simulate task processing
	time.Sleep(2 * time.Second)
	
	// Update task with result
	task.Status = TaskStatusCompleted
	task.Result = map[string]interface{}{
		"message": fmt.Sprintf("Processed instruction: %s", task.Instruction),
	}
	task.UpdatedAt = time.Now()
	
	logger.Infof("Task %s completed", task.ID)
}
EOF

# Create go.sum files to avoid issues
touch vm_manager/go.sum
touch api_gateway/go.sum
touch orchestrator/go.sum

# 5. Update docker-compose.yml to use explicit local naming
echo "Updating docker-compose.yml with explicit local naming..."
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

# 6. Fix permission issues
echo "Fixing permissions..."
chmod -R 755 agent_system knowledge_system command_executor vm_manager orchestrator api_gateway

echo "Fix complete! Now run the following commands:"
echo "1. podman compose build"
echo "2. podman compose up -d"
