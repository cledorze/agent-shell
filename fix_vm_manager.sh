#!/bin/bash

echo "Creating corrected VM Manager structure and files..."

# Create the correct directory structure
mkdir -p vm_manager/cmd/vm_manager
mkdir -p vm_manager/internal/vm

# Create the main.go file with correct import paths
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

func main() {
	logger.SetFormatter(&logrus.TextFormatter{
		FullTimestamp: true,
	})
	logger.Info("Starting VM Manager service")

	// Initialize connection to libvirt
	connURI := os.Getenv("LIBVIRT_CONNECTION")
	if connURI == "" {
		connURI = "qemu:///system"
	}
	logger.Infof("Connecting to libvirt: %s", connURI)

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

// VM representation
type VM struct {
	Name      string   `json:"name"`
	Status    string   `json:"status"`
	IPAddress []string `json:"ipAddress,omitempty"`
}

// Mock handlers for development/testing
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

# Create a simple vm package in the internal directory
cat > vm_manager/internal/vm/manager.go << 'EOF'
package vm

import (
	"fmt"
)

// Manager handles VM operations
type Manager struct {
	ConnURI string
}

// NewManager creates a new VM manager
func NewManager(connURI string) (*Manager, error) {
	if connURI == "" {
		connURI = "qemu:///system"
	}
	
	return &Manager{
		ConnURI: connURI,
	}, nil
}

// ListVMs returns a list of VMs
func (m *Manager) ListVMs() ([]string, error) {
	// In a real implementation, this would use libvirt to list VMs
	return []string{"openSUSE-1", "openSUSE-2"}, nil
}

// StartVM starts a VM
func (m *Manager) StartVM(name string) error {
	// In a real implementation, this would use libvirt to start a VM
	fmt.Printf("Starting VM: %s\n", name)
	return nil
}

// StopVM stops a VM
func (m *Manager) StopVM(name string) error {
	// In a real implementation, this would use libvirt to stop a VM
	fmt.Printf("Stopping VM: %s\n", name)
	return nil
}

// RestartVM restarts a VM
func (m *Manager) RestartVM(name string) error {
	// In a real implementation, this would use libvirt to restart a VM
	fmt.Printf("Restarting VM: %s\n", name)
	return nil
}
EOF

# Update go.mod to use local modules
cat > vm_manager/go.mod << 'EOF'
module vm_manager

go 1.19

require (
	github.com/gorilla/mux v1.8.0
	github.com/sirupsen/logrus v1.9.0
)

require golang.org/x/sys v0.0.0-20220715151400-c0bba94af5f8 // indirect
EOF

# Create an empty go.sum file
touch vm_manager/go.sum

# Fix permissions for Python applications again to be sure
chmod -R 755 agent_system knowledge_system

echo "VM Manager fix complete. Now try 'podman compose build'"
