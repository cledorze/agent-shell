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
