package main

import (
	"encoding/json"
	"log"
	"net/http"

	"github.com/gorilla/mux"
	"github.com/user/linux-agent-system/vm-manager/internal/libvirt"
)

// HTTPHandler encapsulates HTTP handlers for the VM Manager API
type HTTPHandler struct {
	vmManager *libvirt.VMManager
	logger    *log.Logger
}

// NewHTTPHandler creates a new HTTP handler
func NewHTTPHandler(vmManager *libvirt.VMManager, logger *log.Logger) *HTTPHandler {
	return &HTTPHandler{
		vmManager: vmManager,
		logger:    logger,
	}
}

// SetupRoutes configures the HTTP routes
func (h *HTTPHandler) SetupRoutes(r *mux.Router) {
	// VM management routes
	r.HandleFunc("/vms", h.handleListVMs).Methods("GET")
	r.HandleFunc("/vms", h.handleCreateVM).Methods("POST")
	r.HandleFunc("/vms/{vmId}", h.handleGetVM).Methods("GET")
	r.HandleFunc("/vms/{vmId}", h.handleDestroyVM).Methods("DELETE")
	r.HandleFunc("/vms/{vmId}/reset", h.handleResetVM).Methods("POST")
	
	// Task-VM association
	r.HandleFunc("/tasks/{taskId}/vm", h.handleGetVMByTask).Methods("GET")
	
	// Health check
	r.HandleFunc("/health", h.handleHealthCheck).Methods("GET")
}

// handleListVMs returns a list of all VMs
func (h *HTTPHandler) handleListVMs(w http.ResponseWriter, r *http.Request) {
	vms := h.vmManager.ListVMs()
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"vms":   vms,
		"count": len(vms),
	})
}

// handleCreateVM creates a new VM for a task
func (h *HTTPHandler) handleCreateVM(w http.ResponseWriter, r *http.Request) {
	var request struct {
		TaskID string `json:"task_id"`
	}
	
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}
	
	if request.TaskID == "" {
		http.Error(w, "Task ID is required", http.StatusBadRequest)
		return
	}
	
	vm, err := h.vmManager.CreateVM(request.TaskID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(vm)
}

// handleGetVM returns information about a specific VM
func (h *HTTPHandler) handleGetVM(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	vmID := vars["vmId"]
	
	vm, err := h.vmManager.GetVM(vmID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(vm)
}

// handleDestroyVM destroys a VM
func (h *HTTPHandler) handleDestroyVM(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	vmID := vars["vmId"]
	
	err := h.vmManager.DestroyVM(vmID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status":  "destroying",
		"message": "VM is being destroyed",
		"vm_id":   vmID,
	})
}

// handleResetVM resets a VM to a clean state
func (h *HTTPHandler) handleResetVM(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	vmID := vars["vmId"]
	
	var request struct {
		Force bool `json:"force"`
	}
	
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		// If no body or invalid JSON, assume non-forced reset
		request.Force = false
	}
	
	err := h.vmManager.ResetVM(vmID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status":  "resetting",
		"message": "VM is being reset",
		"vm_id":   vmID,
	})
}

// handleGetVMByTask returns information about a VM associated with a task
func (h *HTTPHandler) handleGetVMByTask(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskID := vars["taskId"]
	
	vm, err := h.vmManager.GetVMByTask(taskID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(vm)
}

// handleHealthCheck returns the health status of the VM Manager
func (h *HTTPHandler) handleHealthCheck(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"status":  "healthy",
		"version": "1.0.0",
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}
