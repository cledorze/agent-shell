package main

import (
	"encoding/json"
	"fmt"
	"bytes"
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
			io.NopCloser(bytes.NewReader(body)))
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
