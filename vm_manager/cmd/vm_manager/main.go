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
