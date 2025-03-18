package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"

	"github.com/gorilla/mux"
)

// VM represents a virtual machine
type VM struct {
	ID        string   `json:"id"`
	Name      string   `json:"name"`
	Status    string   `json:"status"`
	IPAddress []string `json:"ipAddress,omitempty"`
}

func main() {
	log.Println("Starting VM Manager service")

	router := mux.NewRouter()
	router.HandleFunc("/vms", listVMsHandler).Methods("GET")
	router.HandleFunc("/vms/{id}", getVMHandler).Methods("GET")
	router.HandleFunc("/health", healthCheckHandler).Methods("GET")

	port := "8083"
	log.Printf("VM Manager listening on port %s", port)
	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%s", port), router))
}

func listVMsHandler(w http.ResponseWriter, r *http.Request) {
	vms := []VM{
		{ID: "vm1", Name: "openSUSE-1", Status: "running", IPAddress: []string{"192.168.122.100"}},
		{ID: "vm2", Name: "openSUSE-2", Status: "stopped"},
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"vms": vms,
	})
}

func getVMHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	
	vm := VM{ID: id, Name: "openSUSE-" + id, Status: "running", IPAddress: []string{"192.168.122.100"}}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(vm)
}

func healthCheckHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "healthy"})
}
