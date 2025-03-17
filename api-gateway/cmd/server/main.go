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
