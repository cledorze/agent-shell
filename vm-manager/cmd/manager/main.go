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
	"regexp"
	"strings"
	"sync"
	"time"
	"math/rand"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/libvirt/libvirt-go"
)

// VM states
const (
	VMStateCreating   = "creating"
	VMStateRunning    = "running"
	VMStateStopped    = "stopped"
	VMStateError      = "error"
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
	libvirtURI  string
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

	// Create VM instances directory
	instancesDir := filepath.Join(baseDir, "vm-instances")
	if err := os.MkdirAll(instancesDir, 0755); err != nil {
		log.Printf("Failed to create VM instances directory: %v", err)
	}

	// Get the template VM path from environment or use default
	templateVM := os.Getenv("VM_TEMPLATE_PATH")
	if templateVM == "" {
		templateVM = "/app/data/templates/opensuse-tumbleweed.qcow2"
	}

	// Get libvirt URI from environment or use default
	libvirtURI := os.Getenv("LIBVIRT_URI")
	if libvirtURI == "" {
		libvirtURI = "qemu:///system"
	}

	// Verify libvirt connection
	conn, err := libvirt.NewConnect(libvirtURI)
	if err != nil {
		log.Printf("WARNING: Could not connect to libvirt: %v", err)
		log.Printf("Trying to use virsh command line as fallback")
		// Try virsh as fallback
		cmd := exec.Command("virsh", "--version")
		if err := cmd.Run(); err != nil {
			log.Printf("WARNING: virsh command not available: %v", err)
			log.Printf("VM management will be limited")
		} else {
			log.Printf("virsh command is available, will use CLI fallback")
		}
	} else {
		hypervisor, _ := conn.GetType()
		version, _ := conn.GetVersion()
		log.Printf("Connected to libvirt: %s version %d", hypervisor, version)
		conn.Close()
	}

	return &VMManager{
		VMs:         make(map[string]*VM),
		TaskToVMMap: make(map[string]string),
		baseDir:     baseDir,
		templateVM:  templateVM,
		libvirtURI:  libvirtURI,
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
			
			// Verify if the VM actually exists in libvirt
			exists, _ := m.checkVMExists(vm.Name)
			if !exists && vm.State != VMStateDestroying && vm.State != VMStateError {
				log.Printf("VM %s exists in database but not in libvirt. Marking as error.", vm.Name)
				vm.State = VMStateError
				vm.Error = "VM not found in libvirt"
				m.saveVM(&vm)
			}
		}
	}

	return nil
}

// Check if VM exists in libvirt
func (m *VMManager) checkVMExists(vmName string) (bool, error) {
	// Try libvirt API first
	conn, err := libvirt.NewConnect(m.libvirtURI)
	if err == nil {
		defer conn.Close()
		
		domain, err := conn.LookupDomainByName(vmName)
		if err == nil {
			domain.Free()
			return true, nil
		}
		return false, nil
	}
	
	// Fallback to virsh command
	cmd := exec.Command("virsh", "dominfo", vmName)
	err = cmd.Run()
	return err == nil, nil
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
		Name:        fmt.Sprintf("suse-agent-%s", uuid.New().String()[:8]),
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

// Generate random MAC address
func generateRandomMAC() string {
	buf := make([]byte, 6)
	_, err := rand.Read(buf)
	if err != nil {
		return "52:54:00:00:00:01" // Fallback
	}
	
	// Ensure it's a valid MAC for VMs
	buf[0] = (buf[0] & 0xfe) | 0x02 // Set the locally administered bit
	
	return fmt.Sprintf("52:54:%02x:%02x:%02x:%02x", 
		buf[2], buf[3], buf[4], buf[5])
}

// Set up ngrok tunnel
func (m *VMManager) setupNgrokTunnel(ipAddress string, port int) (string, error) {
	// Check if ngrok auth token is available
	authToken := os.Getenv("NGROK_AUTH_TOKEN")
	if authToken == "" {
		return "", fmt.Errorf("NGROK_AUTH_TOKEN not set")
	}
	
	// Set target for tunnel
	target := fmt.Sprintf("%s:%d", ipAddress, port)
	
	// Use ngrok's API to establish a tunnel
	ngrokRegion := os.Getenv("NGROK_REGION")
	if ngrokRegion == "" {
		ngrokRegion = "us"
	}
	
	// Start ngrok in background
	cmd := exec.Command("ngrok", "tcp", "--region", ngrokRegion, "--authtoken", authToken, target)
	if err := cmd.Start(); err != nil {
		return "", fmt.Errorf("failed to start ngrok: %v", err)
	}
	
	// Wait for tunnel to be established
	time.Sleep(5 * time.Second)
	
	// Query ngrok API to get tunnel URL
	resp, err := http.Get("http://localhost:4040/api/tunnels")
	if err != nil {
		return "", fmt.Errorf("failed to query ngrok API: %v", err)
	}
	defer resp.Body.Close()
	
	var result struct {
		Tunnels []struct {
			PublicURL string `json:"public_url"`
			Proto     string `json:"proto"`
		} `json:"tunnels"`
	}
	
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("failed to parse ngrok API response: %v", err)
	}
	
	// Find TCP tunnel
	for _, tunnel := range result.Tunnels {
		if tunnel.Proto == "tcp" {
			return tunnel.PublicURL, nil
		}
	}
	
	return "", fmt.Errorf("no TCP tunnel found")
}

// Provision the VM using libvirt
func (m *VMManager) provisionVM(vm *VM) {
	// Create VM directory
	vmDir := filepath.Join(m.baseDir, "vm-instances", vm.ID)
	if err := os.MkdirAll(vmDir, 0755); err != nil {
		log.Printf("Failed to create VM directory: %v", err)
		m.setVMError(vm, fmt.Sprintf("Failed to create VM directory: %v", err))
		return
	}

	// Set up a VM disk by copying the template
	vmDiskPath := filepath.Join(vmDir, "disk.qcow2")
	log.Printf("Creating VM disk from template %s to %s", m.templateVM, vmDiskPath)
	
	cmd := exec.Command("cp", m.templateVM, vmDiskPath)
	if err := cmd.Run(); err != nil {
		log.Printf("Failed to create VM disk: %v", err)
		m.setVMError(vm, fmt.Sprintf("Failed to create VM disk: %v", err))
		return
	}

	// Try to use libvirt API
	useLibvirtAPI := true
	conn, err := libvirt.NewConnect(m.libvirtURI)
	if err != nil {
		log.Printf("Failed to connect to libvirt API: %v", err)
		log.Printf("Will try using virsh CLI instead")
		useLibvirtAPI = false
	}
	
	// Generate random MAC address
	mac := generateRandomMAC()
	
	if useLibvirtAPI {
		defer conn.Close()
		
		// Create XML definition for the domain
		xmlConfig := fmt.Sprintf(`
		<domain type='kvm'>
		  <name>%s</name>
		  <memory unit='GiB'>2</memory>
		  <vcpu>2</vcpu>
		  <os>
			<type arch='x86_64'>hvm</type>
			<boot dev='hd'/>
		  </os>
		  <features>
			<acpi/>
			<apic/>
		  </features>
		  <devices>
			<disk type='file' device='disk'>
			  <driver name='qemu' type='qcow2'/>
			  <source file='%s'/>
			  <target dev='vda' bus='virtio'/>
			</disk>
			<interface type='network'>
			  <source network='default'/>
			  <mac address='%s'/>
			  <model type='virtio'/>
			</interface>
			<console type='pty'/>
			<graphics type='vnc' port='-1' autoport='yes' listen='0.0.0.0'>
			  <listen type='address' address='0.0.0.0'/>
			</graphics>
		  </devices>
		</domain>`, vm.Name, vmDiskPath, mac)

		// Define the domain
		domain, err := conn.DomainDefineXML(xmlConfig)
		if err != nil {
			log.Printf("Failed to define domain: %v", err)
			m.setVMError(vm, fmt.Sprintf("Failed to define domain: %v", err))
			return
		}

		// Start the domain
		if err := domain.Create(); err != nil {
			log.Printf("Failed to start domain: %v", err)
			m.setVMError(vm, fmt.Sprintf("Failed to start domain: %v", err))
			return
		}
		
		log.Printf("Successfully started VM %s using libvirt API", vm.Name)
	} else {
		// Try using virsh command line
		xmlPath := filepath.Join(vmDir, "domain.xml")
		xmlContent := fmt.Sprintf(`
		<domain type='kvm'>
		  <name>%s</name>
		  <memory unit='GiB'>2</memory>
		  <vcpu>2</vcpu>
		  <os>
			<type arch='x86_64'>hvm</type>
			<boot dev='hd'/>
		  </os>
		  <features>
			<acpi/>
			<apic/>
		  </features>
		  <devices>
			<disk type='file' device='disk'>
			  <driver name='qemu' type='qcow2'/>
			  <source file='%s'/>
			  <target dev='vda' bus='virtio'/>
			</disk>
			<interface type='network'>
			  <source network='default'/>
			  <mac address='%s'/>
			  <model type='virtio'/>
			</interface>
			<console type='pty'/>
			<graphics type='vnc' port='-1' autoport='yes' listen='0.0.0.0'>
			  <listen type='address' address='0.0.0.0'/>
			</graphics>
		  </devices>
		</domain>`, vm.Name, vmDiskPath, mac)
		
		if err := os.WriteFile(xmlPath, []byte(xmlContent), 0644); err != nil {
			log.Printf("Failed to write domain XML: %v", err)
			m.setVMError(vm, fmt.Sprintf("Failed to write domain XML: %v", err))
			return
		}
		
		// Define the domain
		cmd = exec.Command("virsh", "define", xmlPath)
		if output, err := cmd.CombinedOutput(); err != nil {
			log.Printf("Failed to define domain: %v, output: %s", err, output)
			m.setVMError(vm, fmt.Sprintf("Failed to define domain: %v", err))
			return
		}
		
		// Start the domain
		cmd = exec.Command("virsh", "start", vm.Name)
		if output, err := cmd.CombinedOutput(); err != nil {
			log.Printf("Failed to start domain: %v, output: %s", err, output)
			m.setVMError(vm, fmt.Sprintf("Failed to start domain: %v", err))
			return
		}
		
		log.Printf("Successfully started VM %s using virsh command line", vm.Name)
	}
	
	// Wait for VM to boot and get IP address
	var ip string
	var ipErr error
	
	if useLibvirtAPI {
		domain, err := conn.LookupDomainByName(vm.Name)
		if err != nil {
			log.Printf("Failed to lookup domain: %v", err)
			ip, ipErr = m.waitForIPUsingARP(vm.Name, mac, 5*time.Minute)
		} else {
			ip, ipErr = m.waitForIPUsingLibvirt(domain, 5*time.Minute)
			domain.Free()
		}
	} else {
		ip, ipErr = m.waitForIPUsingARP(vm.Name, mac, 5*time.Minute)
	}
	
	if ipErr != nil {
		log.Printf("Failed to get VM IP address: %v", ipErr)
		// Set a partial error but continue
		vm.Error = fmt.Sprintf("Warning: Could not determine IP address: %v", ipErr)
	} else {
		vm.IPAddress = ip
		log.Printf("VM %s has IP address: %s", vm.Name, ip)
	}
	
	// Set up ngrok tunnel for remote access
	if ip != "" {
		ngrokURL, err := m.setupNgrokTunnel(ip, 22)
		if err != nil {
			log.Printf("Failed to set up ngrok tunnel: %v", err)
			// Continue anyway, just log the error
			vm.Error = fmt.Sprintf("Warning: Could not establish ngrok tunnel: %v", err)
		} else {
			vm.NgrokUrl = ngrokURL
			log.Printf("Established ngrok tunnel for VM %s: %s", vm.Name, ngrokURL)
		}
	}

	// Update VM state
	m.mutex.Lock()
	vm.State = VMStateRunning
	if vm.Error != "" && !strings.HasPrefix(vm.Error, "Warning:") {
		vm.State = VMStateError
	}
	m.mutex.Unlock()

	// Save VM information
	if err := m.saveVM(vm); err != nil {
		log.Printf("Failed to save VM data: %v", err)
	}

	log.Printf("VM %s is now %s (IP: %s, Ngrok: %s)", vm.Name, vm.State, vm.IPAddress, vm.NgrokUrl)
}

// Wait for VM to get an IP address using libvirt API
func (m *VMManager) waitForIPUsingLibvirt(domain *libvirt.Domain, timeout time.Duration) (string, error) {
	start := time.Now()
	
	for time.Since(start) < timeout {
		// Try to get DHCP lease from libvirt
		ifaces, err := domain.ListAllInterfaceAddresses(libvirt.DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE)
		if err != nil {
			log.Printf("Failed to get interface addresses: %v", err)
			time.Sleep(5 * time.Second)
			continue
		}
		
		// Look for a valid IP address
		for _, iface := range ifaces {
			for _, addr := range iface.Addrs {
				if addr.Type == libvirt.IP_ADDR_TYPE_IPV4 {
					return addr.Addr, nil
				}
			}
		}
		
		time.Sleep(5 * time.Second)
	}
	
	return "", fmt.Errorf("timeout waiting for IP address")
}

// Wait for VM to get an IP address using ARP table
func (m *VMManager) waitForIPUsingARP(vmName string, macAddress string, timeout time.Duration) (string, error) {
	start := time.Now()
	normalizedMAC := strings.ToLower(macAddress)
	
	for time.Since(start) < timeout {
		// Try using the domain name in the ARP table
		out, err := exec.Command("arp", "-an").Output()
		if err == nil {
			lines := strings.Split(string(out), "\n")
			for _, line := range lines {
				if strings.Contains(strings.ToLower(line), normalizedMAC) {
					// Extract IP from ARP output
					re := regexp.MustCompile(`\(([0-9.]+)\)`)
					matches := re.FindStringSubmatch(line)
					if len(matches) > 1 {
						return matches[1], nil
					}
				}
			}
		}
		
		// Try using virsh domifaddr
		out, err = exec.Command("virsh", "domifaddr", vmName).Output()
		if err == nil {
			lines := strings.Split(string(out), "\n")
			for _, line := range lines {
				if strings.Contains(line, "ipv4") {
					fields := strings.Fields(line)
					if len(fields) >= 4 {
						ipWithMask := fields[3]
						return strings.Split(ipWithMask, "/")[0], nil
					}
				}
			}
		}
		
		time.Sleep(5 * time.Second)
	}
	
	return "", fmt.Errorf("timeout waiting for IP address")
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
		log.Printf("Destroying VM %s...", vm.Name)
		
		// Try using libvirt API
		conn, err := libvirt.NewConnect(m.libvirtURI)
		if err == nil {
			defer conn.Close()
			
			// Look up domain by name
			domain, err := conn.LookupDomainByName(vm.Name)
			if err != nil {
				log.Printf("Failed to find domain: %v", err)
			} else {
				// Check if domain is running
				state, _, err := domain.GetState()
				if err == nil && state == libvirt.DOMAIN_RUNNING {
					// Attempt graceful shutdown first
					if err := domain.Shutdown(); err != nil {
						log.Printf("Failed to shutdown domain gracefully: %v", err)
						// Force destroy if shutdown fails
						if err := domain.Destroy(); err != nil {
							log.Printf("Failed to destroy domain: %v", err)
						}
					}
					
					// Wait for shutdown
					for i := 0; i < 30; i++ {
						state, _, err := domain.GetState()
						if err != nil || state == libvirt.DOMAIN_SHUTOFF {
							break
						}
						time.Sleep(1 * time.Second)
					}
				}
				
				// Undefine domain (remove configuration)
				if err := domain.Undefine(); err != nil {
					log.Printf("Failed to undefine domain: %v", err)
				}
				
				domain.Free()
			}
		} else {
			// Use virsh commands as fallback
			log.Printf("Using virsh commands for VM destruction")
			
			// Try to shut down gracefully first
			cmdShutdown := exec.Command("virsh", "shutdown", vm.Name)
			if err := cmdShutdown.Run(); err != nil {
				log.Printf("Failed to shutdown VM gracefully: %v", err)
				
				// Force destroy if shutdown fails
				cmdDestroy := exec.Command("virsh", "destroy", vm.Name)
				if err := cmdDestroy.Run(); err != nil {
					log.Printf("Failed to destroy VM: %v", err)
				}
			}
			
			// Wait a bit for shutdown to complete
			time.Sleep(5 * time.Second)
			
			// Undefine domain
			cmdUndefine := exec.Command("virsh", "undefine", vm.Name)
			if err := cmdUndefine.Run(); err != nil {
				log.Printf("Failed to undefine VM: %v", err)
			}
		}
		
		// Remove VM storage
		vmDiskPath := filepath.Join(m.baseDir, "vm-instances", vmID, "disk.qcow2")
		if err := os.Remove(vmDiskPath); err != nil {
			log.Printf("Failed to remove VM disk: %v", err)
		}
		
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
	
	// Capture task ID for reference
	taskID := vm.TaskID
	
	// Update VM state
	oldState := vm.State
	vm.State = VMStateDestroying
	m.mutex.Unlock()
	
	// Save VM state
	if err := m.saveVM(vm); err != nil {
		log.Printf("Failed to save VM data: %v", err)
	}
	
	// Start VM reset in background
	go func() {
		log.Printf("Resetting VM %s from state %s...", vm.Name, oldState)
		
		// Destroy the existing VM
		if err := m.DestroyVM(vmID); err != nil {
			log.Printf("Error destroying VM during reset: %v", err)
		}
		
		// Wait for destruction to complete
		time.Sleep(5 * time.Second)
		
		// Create a new VM with the same task ID
		if taskID != "" {
			_, err := m.CreateVM(taskID)
			if err != nil {
				log.Printf("Error creating new VM during reset: %v", err)
			}
		}
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
	
	var request struct {
		Force bool `json:"force"`
	}
	
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		// If no body provided, assume non-forced reset
		request.Force = false
	}
	
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
	
	// Test libvirt connection
	libvirtStatus := "unavailable"
	conn, err := libvirt.NewConnect(m.libvirtURI)
	if err == nil {
		libvirtStatus = "connected"
		hypervisor, _ := conn.GetType()
		version, _ := conn.GetVersion()
		libvirtStatus = fmt.Sprintf("connected to %s v%d", hypervisor, version)
		conn.Close()
	} else {
		// Try virsh command line as fallback
		cmd := exec.Command("virsh", "--version")
		if err := cmd.Run(); err == nil {
			libvirtStatus = "available via CLI"
		}
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "healthy",
		"vm_count": vmCount,
		"template_vm": m.templateVM,
		"libvirt_status": libvirtStatus,
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
