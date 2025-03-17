// vm-manager/cmd/manager/main.go
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
)

// VM states
const (
	VMStateCreating = "creating"
	VMStateRunning  = "running"
	VMStateStopped  = "stopped"
	VMStateError    = "error"
	VMStateDestroying = "destroying"
)

// VM represents an OpenSUSE Tumbleweed virtual machine
type VM struct {
	ID          string    `json:"id"`
	TaskID      string    `json:"task_id"`
	Name        string    `json:"name"`
	State       string    `json:"state"`
	IPAddress   string    `json:"ip_address,omitempty"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
	Error       string    `json:"error,omitempty"`
	NgrokUrl    string    `json:"ngrok_url,omitempty"`
	SshUsername string    `json:"ssh_username"`
	SshPassword string    `json:"ssh_password"`
}

// VMManager manages OpenSUSE Tumbleweed VMs
type VMManager struct {
	VMs         map[string]*VM
	TaskToVMMap map[string]string
	baseDir     string
	templateVM  string
	mutex       sync.Mutex
}

// Create a new VM manager
func NewVMManager() *VMManager {
	baseDir := os.Getenv("VM_DATA_DIR")
	if baseDir == "" {
		baseDir = "/app/data/vms"
	}

	// Create the base directory if it doesn't exist
	if err := os.MkdirAll(baseDir, 0755); err != nil {
		log.Printf("Failed to create VM data directory: %v", err)
	}

	// Get the template VM path from environment or use default
	templateVM := os.Getenv("VM_TEMPLATE_PATH")
	if templateVM == "" {
		templateVM = "/app/data/templates/opensuse-tumbleweed.qcow2"
	}

	return &VMManager{
		VMs:         make(map[string]*VM),
		TaskToVMMap: make(map[string]string),
		baseDir:     baseDir,
		templateVM:  templateVM,
	}
}

// Load VM information from file
func (m *VMManager) loadVMs() error {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Ensure VM directory exists
	vmDir := filepath.Join(m.baseDir, "vm-data")
	if err := os.MkdirAll(vmDir, 0755); err != nil {
		return fmt.Errorf("failed to create VM data directory: %w", err)
	}

	// List all VM data files
	files, err := os.ReadDir(vmDir)
	if err != nil {
		return fmt.Errorf("failed to read VM data directory: %w", err)
	}

	// Load VM information
	for _, file := range files {
		if strings.HasSuffix(file.Name(), ".json") {
			vmFile := filepath.Join(vmDir, file.Name())
			data, err := os.ReadFile(vmFile)
			if err != nil {
				log.Printf("Failed to read VM data file %s: %v", vmFile, err)
				continue
			}

			var vm VM
			if err := json.Unmarshal(data, &vm); err != nil {
				log.Printf("Failed to parse VM data file %s: %v", vmFile, err)
				continue
			}

			// Add VM to maps
			m.VMs[vm.ID] = &vm
			if vm.TaskID != "" {
				m.TaskToVMMap[vm.TaskID] = vm.ID
			}

			log.Printf("Loaded VM: %s (State: %s, Task: %s)", vm.Name, vm.State, vm.TaskID)
		}
	}

	return nil
}

// Save VM information to file
func (m *VMManager) saveVM(vm *VM) error {
	vm.UpdatedAt = time.Now()

	// Ensure VM directory exists
	vmDir := filepath.Join(m.baseDir, "vm-data")
	if err := os.MkdirAll(vmDir, 0755); err != nil {
		return fmt.Errorf("failed to create VM data directory: %w", err)
	}

	// Create VM data file
	data, err := json.MarshalIndent(vm, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to serialize VM data: %w", err)
	}

	filename := filepath.Join(vmDir, fmt.Sprintf("%s.json", vm.ID))
	if err := os.WriteFile(filename, data, 0644); err != nil {
		return fmt.Errorf("failed to write VM data: %w", err)
	}

	return nil
}

// Create a new VM for a task
func (m *VMManager) CreateVM(taskID string) (*VM, error) {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Check if a VM already exists for this task
	if vmID, exists := m.TaskToVMMap[taskID]; exists {
		return m.VMs[vmID], nil
	}

	// Create a new VM
	vm := &VM{
		ID:          uuid.New().String(),
		TaskID:      taskID,
		Name:        fmt.Sprintf("suse-agent-vm-%s", taskID[:8]),
		State:       VMStateCreating,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
		SshUsername: "agent",
		SshPassword: uuid.New().String()[:12], // Random password
	}

	// Save VM information
	m.VMs[vm.ID] = vm
	m.TaskToVMMap[taskID] = vm.ID
	if err := m.saveVM(vm); err != nil {
		log.Printf("Failed to save VM data: %v", err)
	}

	// Start VM creation in background
	go m.provisionVM(vm)

	return vm, nil
}

// Provision the VM (this would be a real provisioning in production)
func (m *VMManager) provisionVM(vm *VM) {
	// Create VM directory
	vmDir := filepath.Join(m.baseDir, "vm-instances", vm.ID)
	if err := os.MkdirAll(vmDir, 0755); err != nil {
		log.Printf("Failed to create VM directory: %v", err)
		m.setVMError(vm, fmt.Sprintf("Failed to create VM directory: %v", err))
		return
	}

	// In a real implementation, this would create a real VM
	// For this demo, we'll simulate VM creation with a delay
	log.Printf("Creating VM %s for task %s...", vm.Name, vm.TaskID)
	time.Sleep(5 * time.Second)

	// Set up a VM disk by copying the template
	vmDiskPath := filepath.Join(vmDir, "disk.qcow2")
	cmd := exec.Command("cp", m.templateVM, vmDiskPath)
	if err := cmd.Run(); err != nil {
		log.Printf("Failed to create VM disk: %v", err)
		m.setVMError(vm, fmt.Sprintf("Failed to create VM disk: %v", err))
		return
	}

	// Simulate starting the VM
	log.Printf("Starting VM %s...", vm.Name)
	time.Sleep(3 * time.Second)

	// Update VM state
	m.mutex.Lock()
	vm.State = VMStateRunning
	vm.IPAddress = fmt.Sprintf("192.168.122.%d", 100+len(m.VMs))
	vm.NgrokUrl = fmt.Sprintf("https://%s.ngrok.io", vm.ID[:8])
	m.mutex.Unlock()

	// Save VM information
	if err := m.saveVM(vm); err != nil {
		log.Printf("Failed to save VM data: %v", err)
	}

	log.Printf("VM %s is now running (IP: %s, Ngrok: %s)", vm.Name, vm.IPAddress, vm.NgrokUrl)
}

// Set VM in error state
func (m *VMManager) setVMError(vm *VM, errorMsg string) {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	vm.State = VMStateError
	vm.Error = errorMsg
	vm.UpdatedAt = time.Now()

	if err := m.saveVM(vm); err != nil {
		log.Printf("Failed to save VM error state: %v", err)
	}
}

// Destroy a VM
func (m *VMManager) DestroyVM(vmID string) error {
	m.mutex.Lock()
	
	// Get VM
	vm, exists := m.VMs[vmID]
	if !exists {
		m.mutex.Unlock()
		return fmt.Errorf("VM not found: %s", vmID)
	}
	
	// Update VM state
	vm.State = VMStateDestroying
	m.mutex.Unlock()
	
	// Save VM state
	if err := m.saveVM(vm); err != nil {
		log.Printf("Failed to save VM data: %v", err)
	}
	
	// Start VM destruction in background
	go func() {
		// In production, this would properly shut down and delete the VM
		log.Printf("Destroying VM %s...", vm.Name)
		time.Sleep(2 * time.Second)
		
		m.mutex.Lock()
		defer m.mutex.Unlock()
		
		// Remove from task map
		if vm.TaskID != "" {
			delete(m.TaskToVMMap, vm.TaskID)
		}
		
		// Remove from VM map
		delete(m.VMs, vmID)
		
		// Remove VM data file
		vmFile := filepath.Join(m.baseDir, "vm-data", fmt.Sprintf("%s.json", vmID))
		if err := os.Remove(vmFile); err != nil {
			log.Printf("Failed to remove VM data file: %v", err)
		}
		
		// Remove VM directory
		vmDir := filepath.Join(m.baseDir, "vm-instances", vmID)
		if err := os.RemoveAll(vmDir); err != nil {
			log.Printf("Failed to remove VM directory: %v", err)
		}
		
		log.Printf("VM %s destroyed", vm.Name)
	}()
	
	return nil
}

// Get VM by ID
func (m *VMManager) GetVM(vmID string) (*VM, error) {
	m.mutex.Lock()
	defer m.mutex.Unlock()
	
	vm, exists := m.VMs[vmID]
	if !exists {
		return nil, fmt.Errorf("VM not found: %s", vmID)
	}
	
	return vm, nil
}

// Get VM by task ID
func (m *VMManager) GetVMByTask(taskID string) (*VM, error) {
	m.mutex.Lock()
	defer m.mutex.Unlock()
	
	vmID, exists := m.TaskToVMMap[taskID]
	if !exists {
		return nil, fmt.Errorf("no VM found for task: %s", taskID)
	}
	
	vm, exists := m.VMs[vmID]
	if !exists {
		return nil, fmt.Errorf("VM not found: %s", vmID)
	}
	
	return vm, nil
}

// Reset a VM to clean state
func (m *VMManager) ResetVM(vmID string) error {
	m.mutex.Lock()
	
	// Get VM
	vm, exists := m.VMs[vmID]
	if !exists {
		m.mutex.Unlock()
		return fmt.Errorf("VM not found: %s", vmID)
	}
	
	// Update VM state
	oldState := vm.State
	vm.State = VMStateCreating
	vm.Error = ""
	m.mutex.Unlock()
	
	// Save VM state
	if err := m.saveVM(vm); err != nil {
		log.Printf("Failed to save VM data: %v", err)
	}
	
	// Start VM reset in background
	go func() {
		log.Printf("Resetting VM %s from state %s...", vm.Name, oldState)
		
		// In production, this would properly reset the VM to a clean state
		// For this demo, we'll simulate VM reset with a delay
		time.Sleep(5 * time.Second)
		
		// Update VM state
		m.mutex.Lock()
		vm.State = VMStateRunning
		m.mutex.Unlock()
		
		// Save VM information
		if err := m.saveVM(vm); err != nil {
			log.Printf("Failed to save VM data: %v", err)
		}
		
		log.Printf("VM %s has been reset", vm.Name)
	}()
	
	return nil
}

// List all VMs
func (m *VMManager) ListVMs() []*VM {
	m.mutex.Lock()
	defer m.mutex.Unlock()
	
	vms := make([]*VM, 0, len(m.VMs))
	for _, vm := range m.VMs {
		vms = append(vms, vm)
	}
	
	return vms
}

// HTTP handler for creating a VM
func (m *VMManager) handleCreateVM(w http.ResponseWriter, r *http.Request) {
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
	
	vm, err := m.CreateVM(request.TaskID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(vm)
}

// HTTP handler for getting a VM
func (m *VMManager) handleGetVM(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	vmID := vars["vmId"]
	
	vm, err := m.GetVM(vmID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(vm)
}

// HTTP handler for getting a VM by task ID
func (m *VMManager) handleGetVMByTask(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskID := vars["taskId"]
	
	vm, err := m.GetVMByTask(taskID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(vm)
}

// HTTP handler for destroying a VM
func (m *VMManager) handleDestroyVM(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	vmID := vars["vmId"]
	
	if err := m.DestroyVM(vmID); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "destroying",
		"message": "VM is being destroyed",
	})
}

// HTTP handler for resetting a VM
func (m *VMManager) handleResetVM(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	vmID := vars["vmId"]
	
	if err := m.ResetVM(vmID); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "resetting",
		"message": "VM is being reset",
	})
}

// HTTP handler for listing all VMs
func (m *VMManager) handleListVMs(w http.ResponseWriter, r *http.Request) {
	vms := m.ListVMs()
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"vms": vms,
		"count": len(vms),
	})
}

// HTTP handler for health check
func (m *VMManager) handleHealthCheck(w http.ResponseWriter, r *http.Request) {
	m.mutex.Lock()
	vmCount := len(m.VMs)
	m.mutex.Unlock()
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "healthy",
		"vm_count": vmCount,
		"template_vm": m.templateVM,
		"version": "1.0.0",
	})
}

func main() {
	// Load environment variables
	port := os.Getenv("VM_MANAGER_PORT")
	if port == "" {
		port = "8083"
	}
	
	// Create VM manager
	manager := NewVMManager()
	
	// Load existing VMs
	if err := manager.loadVMs(); err != nil {
		log.Printf("Failed to load VMs: %v", err)
	}
	
	// Create router
	r := mux.NewRouter()
	
	// API routes
	r.HandleFunc("/vms", manager.handleListVMs).Methods("GET")
	r.HandleFunc("/vms", manager.handleCreateVM).Methods("POST")
	r.HandleFunc("/vms/{vmId}", manager.handleGetVM).Methods("GET")
	r.HandleFunc("/vms/{vmId}", manager.handleDestroyVM).Methods("DELETE")
	r.HandleFunc("/vms/{vmId}/reset", manager.handleResetVM).Methods("POST")
	r.HandleFunc("/tasks/{taskId}/vm", manager.handleGetVMByTask).Methods("GET")
	r.HandleFunc("/health", manager.handleHealthCheck).Methods("GET")
	
	// Start server
	log.Printf("VM Manager starting on port %s", port)
	if err := http.ListenAndServe(":"+port, r); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
