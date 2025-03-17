#!/bin/bash

# Linux Agent System Setup Script
# This script creates the complete project structure and initializes the main files

set -e  # Stop execution on error

# Colors for messages
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Creating Linux Agent System Project ===${NC}"

# Installation path
PROJECT_DIR="linux-agent-system"
read -p "Installation path [$PROJECT_DIR]: " custom_dir
PROJECT_DIR=${custom_dir:-$PROJECT_DIR}

# Create main directory
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"
echo -e "${GREEN}Main directory created at $(pwd)${NC}"

# Create base structure
echo -e "${YELLOW}Creating directory structure...${NC}"

# Main directories
mkdir -p docs
mkdir -p api-gateway/{cmd/server,internal/{config,handlers,middleware,models},pkg/utils}
mkdir -p orchestrator/{cmd/orchestrator,internal/{config,service,models},pkg/utils}
mkdir -p vm-manager/{cmd/manager,internal/{config,vm,state,models},pkg/utils}
mkdir -p agent-system/{config,agents,knowledge,utils,tests}
mkdir -p command-executor/{src,tests}
mkdir -p knowledge-system/{data/opensuse-docs,src,scripts}

# Add docker-compose, Makefile, etc.
echo -e "${YELLOW}Creating configuration files...${NC}"

# Create README.md
cat > README.md << 'EOF'
# Linux Agent System

Autonomous agent system for managing and configuring OpenSUSE Tumbleweed Linux machines.

## Features

- Process natural language instructions for system administration
- VM orchestration with automatic reset capabilities
- Contextual documentation search for precise execution
- Secure remote command execution via ngrok

## Architecture

The system consists of several components:

1. API Gateway (Go) - Entry point for requests
2. Orchestrator (Go) - Agent work coordination
3. Agent System (Python) - Intelligent task processing
4. VM Manager (Go) - Virtual machine lifecycle management
5. Command Executor (Rust) - Secure command execution
6. Knowledge System - Information storage and retrieval

## Installation

```bash
# Clone the repository
git clone https://github.com/user/linux-agent-system.git
cd linux-agent-system

# Configure environment variables
cp .env.example .env
nano .env  # Modify according to your needs

# Build and start services
make build
make run
```

## Usage

```bash
# Example of sending an instruction
curl -X POST http://localhost:8080/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"task": "Install nginx and configure it to start at boot"}'
```

## Development

```bash
# Run tests
make test

# Build a specific component
make build-api-gateway
```

## License

MIT
EOF

# Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  api-gateway:
    build: ./api-gateway
    ports:
      - "8080:8080"
    environment:
      - ORCHESTRATOR_URL=http://orchestrator:8081
    depends_on:
      - orchestrator
    volumes:
      - api_data:/app/data
    restart: unless-stopped

  orchestrator:
    build: ./orchestrator
    ports:
      - "8081:8081"
    environment:
      - AGENT_SYSTEM_URL=http://agent-system:8082
      - VM_MANAGER_URL=http://vm-manager:8083
    depends_on:
      - agent-system
      - vm-manager
    volumes:
      - orchestrator_data:/app/data
    restart: unless-stopped

  agent-system:
    build: ./agent-system
    ports:
      - "8082:8082"
    environment:
      - KNOWLEDGE_SYSTEM_URL=http://knowledge-system:8084
      - COMMAND_EXECUTOR_URL=http://command-executor:8085
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - knowledge-system
      - command-executor
    volumes:
      - agent_data:/app/data
    restart: unless-stopped

  vm-manager:
    build: ./vm-manager
    ports:
      - "8083:8083"
    volumes:
      - vm_data:/app/data
      - /var/run/libvirt:/var/run/libvirt  # To access libvirt on the host
    restart: unless-stopped

  command-executor:
    build: ./command-executor
    ports:
      - "8085:8085"
    environment:
      - NGROK_AUTH_TOKEN=${NGROK_AUTH_TOKEN}
    volumes:
      - executor_data:/app/data
    restart: unless-stopped

  knowledge-system:
    build: ./knowledge-system
    ports:
      - "8084:8084"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANYTHINGLLM_URL=${ANYTHINGLLM_URL}
      - ANYTHINGLLM_API_KEY=${ANYTHINGLLM_API_KEY}
    volumes:
      - knowledge_data:/app/data
    restart: unless-stopped

volumes:
  api_data:
  orchestrator_data:
  agent_data:
  vm_data:
  executor_data:
  knowledge_data:
EOF

# Create Makefile
cat > Makefile << 'EOF'
.PHONY: build run stop clean test build-api-gateway build-orchestrator build-vm-manager build-agent-system build-command-executor build-knowledge-system

# Variables
DOCKER_COMPOSE = docker-compose
PROJECT_NAME = linux-agent-system

# Main commands
build:
	$(DOCKER_COMPOSE) build

run:
	$(DOCKER_COMPOSE) up -d

stop:
	$(DOCKER_COMPOSE) down

clean:
	$(DOCKER_COMPOSE) down -v

test:
	cd api-gateway && go test ./...
	cd orchestrator && go test ./...
	cd vm-manager && go test ./...
	cd agent-system && python -m pytest
	cd command-executor && cargo test
	cd knowledge-system && python -m pytest

# Build individual components
build-api-gateway:
	$(DOCKER_COMPOSE) build api-gateway

build-orchestrator:
	$(DOCKER_COMPOSE) build orchestrator

build-vm-manager:
	$(DOCKER_COMPOSE) build vm-manager

build-agent-system:
	$(DOCKER_COMPOSE) build agent-system

build-command-executor:
	$(DOCKER_COMPOSE) build command-executor

build-knowledge-system:
	$(DOCKER_COMPOSE) build knowledge-system

# Documentation
docs:
	cd docs && mkdocs build

serve-docs:
	cd docs && mkdocs serve
EOF

# Create .env.example
cat > .env.example << 'EOF'
# General configuration
LOG_LEVEL=info

# API Gateway
API_PORT=8080

# OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# ngrok
NGROK_AUTH_TOKEN=your_ngrok_token_here
NGROK_REGION=eu

# AnythingLLM
ANYTHINGLLM_URL=http://anythingllm:3001
ANYTHINGLLM_API_KEY=your_anythingllm_api_key_here

# Orchestrator
ORCHESTRATOR_PORT=8081

# VM Manager
VM_MANAGER_PORT=8083
LIBVIRT_URI=qemu:///system

# Command Executor
COMMAND_EXECUTOR_PORT=8085
EOF

# Create api-gateway/Dockerfile
mkdir -p api-gateway
cat > api-gateway/Dockerfile << 'EOF'
FROM golang:1.21-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o api-gateway ./cmd/server

FROM alpine:3.18

RUN apk --no-cache add ca-certificates

WORKDIR /app/
COPY --from=builder /app/api-gateway .

EXPOSE 8080
CMD ["./api-gateway"]
EOF

# Create api-gateway/go.mod
cat > api-gateway/go.mod << 'EOF'
module github.com/user/linux-agent-system/api-gateway

go 1.21

require (
	github.com/gorilla/mux v1.8.1
	github.com/joho/godotenv v1.5.1
	github.com/prometheus/client_golang v1.18.0
)
EOF

# Create orchestrator/Dockerfile
mkdir -p orchestrator
cat > orchestrator/Dockerfile << 'EOF'
FROM golang:1.21-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o orchestrator ./cmd/orchestrator

FROM alpine:3.18

RUN apk --no-cache add ca-certificates

WORKDIR /app/
COPY --from=builder /app/orchestrator .

EXPOSE 8081
CMD ["./orchestrator"]
EOF

# Create vm-manager/Dockerfile
mkdir -p vm-manager
cat > vm-manager/Dockerfile << 'EOF'
FROM golang:1.21-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o vm-manager ./cmd/manager

FROM alpine:3.18

RUN apk --no-cache add ca-certificates libvirt-client

WORKDIR /app/
COPY --from=builder /app/vm-manager .

EXPOSE 8083
CMD ["./vm-manager"]
EOF

# Create agent-system/Dockerfile
mkdir -p agent-system
cat > agent-system/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8082
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8082"]
EOF

# Create agent-system/requirements.txt
cat > agent-system/requirements.txt << 'EOF'
fastapi==0.110.0
uvicorn==0.27.1
pydantic==2.6.1
openai==1.12.0
langchain==0.1.0
chromadb==0.4.22
tiktoken==0.5.2
python-dotenv==1.0.0
pytest==7.4.3
requests==2.31.0
numpy==1.26.3
tenacity==8.2.3
EOF

# Create command-executor/Dockerfile
mkdir -p command-executor
cat > command-executor/Dockerfile << 'EOF'
FROM rust:1.75 as builder

WORKDIR /app

COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo 'fn main() { println!("Placeholder"); }' > src/main.rs
RUN cargo build --release
RUN rm -f target/release/deps/command_executor*

COPY . .
RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    openssl \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/target/release/command-executor .

EXPOSE 8085
CMD ["./command-executor"]
EOF

# Create command-executor/Cargo.toml
cat > command-executor/Cargo.toml << 'EOF'
[package]
name = "command-executor"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1.34.0", features = ["full"] }
axum = "0.7.2"
serde = { version = "1.0.193", features = ["derive"] }
serde_json = "1.0.108"
tracing = "0.1.40"
tracing-subscriber = { version = "0.3.18", features = ["env-filter"] }
tower-http = { version = "0.5.0", features = ["trace", "cors"] }
anyhow = "1.0.75"
thiserror = "1.0.50"
dotenv = "0.15.0"
regex = "1.10.2"
reqwest = { version = "0.11.22", features = ["json"] }
chrono = { version = "0.4.31", features = ["serde"] }
uuid = { version = "1.6.1", features = ["v4", "serde"] }
EOF

# Create knowledge-system/Dockerfile
mkdir -p knowledge-system
cat > knowledge-system/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8084
CMD ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8084"]
EOF

# Create knowledge-system/requirements.txt
cat > knowledge-system/requirements.txt << 'EOF'
fastapi==0.110.0
uvicorn==0.27.1
pydantic==2.6.1
openai==1.12.0
langchain==0.1.0
chromadb==0.4.22
tiktoken==0.5.2
python-dotenv==1.0.0
beautifulsoup4==4.12.2
requests==2.31.0
pytest==7.4.3
numpy==1.26.3
tenacity==8.2.3
EOF

# Create API Gateway main file
mkdir -p api-gateway/cmd/server
cat > api-gateway/cmd/server/main.go << 'EOF'
package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gorilla/mux"
	"github.com/joho/godotenv"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type Instruction struct {
	Task        string `json:"task"`
	Priority    string `json:"priority,omitempty"`
	Timeout     int    `json:"timeout,omitempty"`
	RequestID   string `json:"request_id,omitempty"`
}

type TaskResponse struct {
	RequestID   string      `json:"request_id"`
	Status      string      `json:"status"`
	Message     string      `json:"message,omitempty"`
	Details     interface{} `json:"details,omitempty"`
	StartedAt   time.Time   `json:"started_at"`
	CompletedAt *time.Time  `json:"completed_at,omitempty"`
}

func main() {
	// Load environment variables
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found, using environment variables")
	}

	port := os.Getenv("API_PORT")
	if port == "" {
		port = "8080"
	}

	// Configure router
	r := mux.NewRouter()
	
	// API Routes
	api := r.PathPrefix("/api/v1").Subrouter()
	api.HandleFunc("/tasks", submitTaskHandler).Methods("POST")
	api.HandleFunc("/tasks/{requestId}", getTaskStatusHandler).Methods("GET")
	api.HandleFunc("/tasks/{requestId}", cancelTaskHandler).Methods("DELETE")
	api.HandleFunc("/health", healthCheckHandler).Methods("GET")
	
	// Prometheus metrics
	r.Handle("/metrics", promhttp.Handler())

	// HTTP server configuration
	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      r,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start server in background
	go func() {
		log.Printf("API Gateway starting on port %s", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Could not start server: %v", err)
		}
	}()

	// Configure graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	
	log.Println("Shutting down server...")
	
	// Deadline for graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	
	if err := srv.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}
	
	log.Println("Server exited properly")
}

func submitTaskHandler(w http.ResponseWriter, r *http.Request) {
	var instruction Instruction
	
	if err := json.NewDecoder(r.Body).Decode(&instruction); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}
	
	if instruction.Task == "" {
		http.Error(w, "Task instruction is required", http.StatusBadRequest)
		return
	}
	
	// Generate request ID if not provided
	if instruction.RequestID == "" {
		instruction.RequestID = time.Now().Format("20060102-150405.000")
	}
	
	// Send task to orchestrator (to be implemented)
	// orchestratorClient.SubmitTask(instruction)
	
	// Create response
	response := TaskResponse{
		RequestID:  instruction.RequestID,
		Status:     "pending",
		Message:    "Task received and being processed",
		StartedAt:  time.Now(),
	}
	
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	json.NewEncoder(w).Encode(response)
}

func getTaskStatusHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	requestID := vars["requestId"]
	
	// Get status from orchestrator (to be implemented)
	// status := orchestratorClient.GetTaskStatus(requestID)
	
	// Example response for demonstration
	now := time.Now()
	response := TaskResponse{
		RequestID:   requestID,
		Status:      "completed",
		Message:     "Task completed successfully",
		Details:     map[string]string{"output": "Package successfully installed"},
		StartedAt:   now.Add(-30 * time.Second),
		CompletedAt: &now,
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func cancelTaskHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	requestID := vars["requestId"]
	
	// Cancel task via orchestrator (to be implemented)
	// success := orchestratorClient.CancelTask(requestID)
	
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{
		"request_id": requestID,
		"status":     "cancelled",
		"message":    "Task has been cancelled",
	})
}

func healthCheckHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "healthy",
		"version": "1.0.0",
	})
}
EOF

# Create Planning Agent
mkdir -p agent-system/agents
cat > agent-system/agents/planning_agent.py << 'EOF'
import logging
import json
import os
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import openai

logger = logging.getLogger(__name__)

class SubTask(BaseModel):
    """Represents a subtask decomposed by the planning agent."""
    id: str
    description: str
    dependencies: List[str] = []
    estimated_complexity: str
    validation_criteria: List[str] = []
    
class TaskPlan(BaseModel):
    """Represents a complete task plan."""
    request_id: str
    original_task: str
    subtasks: List[SubTask]
    estimated_execution_time: int  # in seconds
    potential_issues: List[str] = []
    requires_prerequisites: bool = False
    prerequisites: List[str] = []

class PlanningAgent:
    """
    Agent responsible for decomposing complex tasks into subtasks
    that can be processed by other agents.
    """
    
    def __init__(self, model_name: str = "gpt-4", api_key: Optional[str] = None):
        """
        Initialize the planning agent.
        
        Args:
            model_name: Name of the LLM model to use
            api_key: API key for model access (optional if defined in environment)
        """
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("API key for OpenAI is required")
            
        logger.info(f"PlanningAgent initialized with model {model_name}")
        
    def create_plan(self, request_id: str, task_description: str) -> TaskPlan:
        """
        Creates a detailed execution plan from a task description.
        
        Args:
            request_id: Unique request identifier
            task_description: Task description in natural language
            
        Returns:
            TaskPlan: A structured plan with subtasks and dependencies
        """
        logger.info(f"Creating plan for task: {task_description}")
        
        # Build prompt for LLM
        prompt = self._build_planning_prompt(task_description)
        
        try:
            # Call LLM to generate plan
            response = openai.ChatCompletion.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a Linux system administration expert. Your task is to break down complex Linux administration tasks into clear, logical steps with proper dependencies."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2000,
                api_key=self.api_key
            )
            
            plan_json = response.choices[0].message.content
            # Extract JSON if needed
            if "```json" in plan_json:
                plan_json = plan_json.split("```json")[1].split("```")[0].strip()
            
            # Parse JSON to Python dict
            plan_dict = json.loads(plan_json)
            
            # Convert to Pydantic model
            subtasks = [SubTask(**subtask) for subtask in plan_dict.get("subtasks", [])]
            
            task_plan = TaskPlan(
                request_id=request_id,
                original_task=task_description,
                subtasks=subtasks,
                estimated_execution_time=plan_dict.get("estimated_execution_time", 300),
                potential_issues=plan_dict.get("potential_issues", []),
                requires_prerequisites=plan_dict.get("requires_prerequisites", False),
                prerequisites=plan_dict.get("prerequisites", [])
            )
            
            logger.info(f"Plan created with {len(subtasks)} subtasks")
            return task_plan
            
        except Exception as e:
            logger.error(f"Error creating plan: {str(e)}")
            raise
    
    def _build_planning_prompt(self, task_description: str) -> str:
        """
        Builds the prompt for the LLM to generate a plan.
        
        Args:
            task_description: Task description
            
        Returns:
            str: Formatted prompt
        """
        return f"""
        I need to create a plan to execute the following OpenSUSE Tumbleweed administration task:
        
        TASK: {task_description}
        
        Break this down into logical subtasks with dependencies. For each subtask, provide:
        1. A unique ID
        2. A clear description of what needs to be done
        3. Dependencies (IDs of subtasks that must be completed first)
        4. Estimated complexity (simple, medium, complex)
        5. Validation criteria to confirm completion
        
        Also include:
        - Estimated total execution time (in seconds)
        - Potential issues that might arise
        - Whether any prerequisites are needed
        - List of prerequisites if applicable
        
        Format your response as a JSON object with this structure:
        ```json
        {{
            "subtasks": [
                {{
                    "id": "string",
                    "description": "string",
                    "dependencies": ["string"],
                    "estimated_complexity": "string",
                    "validation_criteria": ["string"]
                }}
            ],
            "estimated_execution_time": number,
            "potential_issues": ["string"],
            "requires_prerequisites": boolean,
            "prerequisites": ["string"]
        }}
        ```
        
        Consider best practices for OpenSUSE Tumbleweed administration.
        """
    
    def refine_plan(self, plan: TaskPlan, feedback: Dict[str, Any]) -> TaskPlan:
        """
        Refines an existing plan based on feedback from other agents.
        
        Args:
            plan: Initial plan
            feedback: Feedback on detected issues
            
        Returns:
            TaskPlan: Updated plan
        """
        logger.info(f"Refining plan based on feedback")
        
        # Logic for improving the plan based on feedback
        # To be implemented as needed
        
        return plan
EOF

# Create Command Executor main file
mkdir -p command-executor/src
cat > command-executor/src/main.rs << 'EOF'
use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use tokio::process::Command;
use tower_http::trace::TraceLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};
use std::collections::HashMap;
use uuid::Uuid;
use std::time::{Duration, Instant};
use tower_http::cors::{Any, CorsLayer};
use chrono::Utc;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct CommandRequest {
    command: String,
    timeout_seconds: Option<u64>,
    working_directory: Option<String>,
    environment: Option<HashMap<String, String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct CommandResult {
    id: String,
    command: String,
    status: CommandStatus,
    stdout: Option<String>,
    stderr: Option<String>,
    exit_code: Option<i32>,
    execution_time_ms: Option<u64>,
    created_at: chrono::DateTime<chrono::Utc>,
    completed_at: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
enum CommandStatus {
    Pending,
    Running,
    Completed,
    Failed,
    TimedOut,
}

struct AppState {
    command_results: Mutex<HashMap<String, CommandResult>>,
}

#[tokio::main]
async fn main() {
    // Initialize logging
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into()),
        ))
        .with(tracing_subscriber::fmt::layer())
        .init();

    // CORS configuration
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    // Create shared state
    let state = Arc::new(AppState {
        command_results: Mutex::new(HashMap::new()),
    });

    // Define routes
    let app = Router::new()
        .route("/", get(|| async { "Command Executor API" }))
        .route("/health", get(health_check))
        .route("/execute", post(execute_command))
        .route("/result/:id", get(get_command_result))
        .layer(TraceLayer::new_for_http())
        .layer(cors)
        .with_state(Arc::clone(&state));

    // Start server
    let port = std::env::var("COMMAND_EXECUTOR_PORT").unwrap_or_else(|_| "8085".to_string());
    let addr = format!("0.0.0.0:{}", port).parse().unwrap();
    tracing::info!("Command Executor listening on {}", addr);
    
    axum::Server::bind(&addr)
        .serve(app.into_make_service())
        .await
        .unwrap();
}

async fn health_check() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "status": "healthy",
        "version": env!("CARGO_PKG_VERSION")
    }))
}

async fn execute_command(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CommandRequest>,
) -> Result<Json<CommandResult>, (StatusCode, String)> {
    // Command validation and sanitization
    if request.command.trim().is_empty() {
        return Err((StatusCode::BAD_REQUEST, "Command cannot be empty".to_string()));
    }

    // Check if command is blacklisted (example)
    let blacklisted_commands = vec!["rm -rf /", "mkfs", "dd if=/dev/zero"];
    for cmd in blacklisted_commands {
        if request.command.contains(cmd) {
            return Err((
                StatusCode::FORBIDDEN,
                "Command contains disallowed operations".to_string(),
            ));
        }
    }

    // Create ID for this execution
    let id = Uuid::new_v4().to_string();
    
    // Register command as pending
    let command_result = CommandResult {
        id: id.clone(),
        command: request.command.clone(),
        status: CommandStatus::Pending,
        stdout: None,
        stderr: None,
        exit_code: None,
        execution_time_ms: None,
        created_at: Utc::now(),
        completed_at: None,
    };
    
    {
        let mut results = state.command_results.lock().
