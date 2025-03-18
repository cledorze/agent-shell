package libvirt

import (
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
	libvirt "github.com/libvirt/libvirt-go"
)

// VM states
const (
	VMStateCreating   = "creating"
	VMStateRunning    = "running"
	VMStateStopped    = "stopped"
	VMStateError      = "error"
	VMStateDestroying = "destroying"
	VMStateResetting  = "resetting"
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
	NgrokURL    string    `json:"ngrok_url,omitempty"`
	SSHUsername string    `json:"ssh_username"`
	SSHPassword string    `json:"ssh_password"`
}

// Config holds configuration for the VM Manager
type Config struct {
	LibvirtURI       string
	BaseDir          string
	TemplatePath     string
	NetworkName      string
	NgrokAuthToken   string
	NgrokRegion      string
	EnableSimulation bool
}

// VMManager manages OpenSUSE Tumbleweed VMs using libvirt
type VMManager struct {
	conn         *libvirt.Connect
	vms          map[string]*VM
	taskToVMMap  map[string]string
	baseDir      string
	templatePath string
	networkName  string
	ngrokAuth    string
	ngrokRegion  string
	mutex        sync.RWMutex
	logger       *log.Logger
	simulation   bool
}

// NewVMManager creates a new VM manager
func NewVMManager(config Config) (*VMManager, error) {
	// Initialize logger
	logger := log.New(os.Stdout, "[VM Manager] ", log.LstdFlags)

	// Create VM data directories
	baseDir := config.BaseDir
	if baseDir == "" {
		baseDir = "/var/lib/linux-agent-system/vms"
	}

	if err := os.MkdirAll(baseDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create VM base directory: %w", err)
	}

	// Create subdirectories
	if err := os.MkdirAll(filepath.Join(baseDir, "instances"), 0755); err != nil {
		return nil, fmt.Errorf("failed to create VM instances directory: %w", err)
	}

	if err := os.MkdirAll(filepath.Join(baseDir, "vm-data"), 0755); err != nil {
		return nil, fmt.Errorf("failed to create VM data directory: %w", err)
	}

	// Initialize VM manager
	manager := &VMManager{
		vms:          make(map[string]*VM),
		taskToVMMap:  make(map[string]string),
		baseDir:      baseDir,
		templatePath: config.TemplatePath,
		networkName:  config.NetworkName,
		ngrokAuth:    config.NgrokAuthToken,
		ngrokRegion:  config.NgrokRegion,
		logger:       logger,
		simulation:   config.EnableSimulation,
	}

	// If simulation is enabled, skip real libvirt connection
	if config.EnableSimulation {
		logger.Printf("Running in simulation mode (no libvirt connection)")
		if err := manager.loadVMs(); err != nil {
			logger.Printf("Warning: Failed to load existing VMs: %v", err)
		}
		return manager, nil
	}

	// Connect to libvirt
	conn, err := libvirt.NewConnect(config.LibvirtURI)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to libvirt: %w", err)
	}

	// Verify hypervisor capabilities
	hv, err := conn.GetType()
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to get hypervisor type: %w", err)
	}

	logger.Printf("Connected to libvirt hypervisor: %s", hv)

	// Verify KVM is available
	caps, err := conn.GetCapabilities()
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to get capabilities: %w", err)
	}

	if !strings.Contains(caps, "<domain type='kvm'>") {
		conn.Close()
		return nil, fmt.Errorf("KVM is not available on this host")
	}

	// Verify template image exists
	if _, err := os.Stat(config.TemplatePath); os.IsNotExist(err) {
		conn.Close()
		return nil, fmt.Errorf("VM template image not found: %s", config.TemplatePath)
	}

	// Set the connection
	manager.conn = conn

	// Load existing VMs
	if err := manager.loadVMs(); err != nil {
		logger.Printf("Warning: Failed to load existing VMs: %v", err)
	}

	// Initialize random number generator
	rand.Seed(time.Now().UnixNano())

	return manager, nil
}

// Close releases resources
func (m *VMManager) Close() error {
	if m.conn != nil {
		return m.conn.Close()
	}
	return nil
}

// loadVMs loads existing VM information from file
func (m *VMManager) loadVMs() error {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Get all VM data files
	vmDir := filepath.Join(m.baseDir, "vm-data")
	files, err := os.ReadDir(vmDir)
	if err != nil {
		if os.IsNotExist(err) {
			return os.MkdirAll(vmDir, 0755)
		}
		return fmt.Errorf("failed to read VM data directory: %w", err)
	}

	// Load VM information
	for _, file := range files {
		if strings.HasSuffix(file.Name(), ".json") {
			vmFile := filepath.Join(vmDir, file.Name())
			data, err := os.ReadFile(vmFile)
			if err != nil {
				m.logger.Printf("Failed to read VM data file %s: %v", vmFile, err)
				continue
			}

			var vm VM
			if err := json.Unmarshal(data, &vm); err != nil {
				m.logger.Printf("Failed to parse VM data file %s: %v", vmFile, err)
				continue
			}

			// Add VM to maps
			m.vms[vm.ID] = &vm
			if vm.TaskID != "" {
				m.taskToVMMap[vm.TaskID] = vm.ID
			}

			m.logger.Printf("Loaded VM: %s (State: %s, Task: %s)", vm.Name, vm.State, vm.TaskID)

			// Verify if VM exists in libvirt (skip in simulation mode)
			if !m.simulation && m.conn != nil && vm.State != VMStateDestroying && vm.State != VMStateError {
				_, err := m.conn.LookupDomainByName(vm.Name)
				if err != nil {
					m.logger.Printf("VM %s exists in database but not in libvirt. Marking as error.", vm.Name)
					vm.State = VMStateError
					vm.Error = "VM not found in libvirt"
					m.saveVM(&vm)
				}
			}
		}
	}

	return nil
}

// saveVM saves VM information to file
func (m *VMManager) saveVM(vm *VM) error {
	// Update timestamp
	vm.UpdatedAt = time.Now()

	// Create VM data file
	data, err := json.MarshalIndent(vm, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to serialize VM data: %w", err)
	}

	// Write to file
	vmFile := filepath.Join(m.baseDir, "vm-data", fmt.Sprintf("%s.json", vm.ID))
	if err := os.WriteFile(vmFile, data, 0644); err != nil {
		return fmt.Errorf("failed to write VM data file: %w", err)
	}

	return nil
}

// setVMError sets a VM to error state with message
func (m *VMManager) setVMError(vm *VM, errorMsg string) {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	m.logger.Printf("Setting VM %s to error state: %s", vm.Name, errorMsg)

	vm.State = VMStateError
	vm.Error = errorMsg
	vm.UpdatedAt = time.Now()

	if err := m.saveVM(vm); err != nil {
		m.logger.Printf("Failed to save VM error state: %v", err)
	}
}

// CreateVM creates a new VM for a task
func (m *VMManager) CreateVM(taskID string) (*VM, error) {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Check if a VM already exists for this task
	if vmID, exists := m.taskToVMMap[taskID]; exists {
		return m.vms[vmID], nil
	}

	// Generate a unique ID and name
	vmID := uuid.New().String()
	vmName := fmt.Sprintf("agent-vm-%s", vmID[:8])

	// Create VM record
	vm := &VM{
		ID:          vmID,
		TaskID:      taskID,
		Name:        vmName,
		State:       VMStateCreating,
		SSHUsername: "agent",
		SSHPassword: generateRandomPassword(16),
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}

	// Add to maps
	m.vms[vmID] = vm
	m.taskToVMMap[taskID] = vmID

	// Save VM state
	if err := m.saveVM(vm); err != nil {
		m.logger.Printf("Warning: Failed to save VM state: %v", err)
	}

	// Start VM provisioning in background
	go m.provisionVM(vm)

	return vm, nil
}

// provisionVM sets up and starts a new VM
func (m *VMManager) provisionVM(vm *VM) {
	// Handle panics
	defer func() {
		if r := recover(); r != nil {
			m.setVMError(vm, fmt.Sprintf("Panic during VM provisioning: %v", r))
		}
	}()

	m.logger.Printf("Provisioning VM %s for task %s", vm.Name, vm.TaskID)

	// In simulation mode, just simulate VM creation
	if m.simulation {
		m.simulateProvisionVM(vm)
		return
	}

	// Create VM directory
	vmDir := filepath.Join(m.baseDir, "instances", vm.ID)
	if err := os.MkdirAll(vmDir, 0755); err != nil {
		m.setVMError(vm, fmt.Sprintf("Failed to create VM directory: %v", err))
		return
	}

	// Create VM disk by cloning template
	diskPath := filepath.Join(vmDir, "disk.qcow2")
	if err := m.cloneTemplateDisk(m.templatePath, diskPath); err != nil {
		m.setVMError(vm, fmt.Sprintf("Failed to clone template disk: %v", err))
		return
	}

	// Generate cloud-init configuration
	cloudInitISOPath, err := m.generateCloudInit(vm, vmDir)
	if err != nil {
		m.setVMError(vm, fmt.Sprintf("Failed to generate cloud-init configuration: %v", err))
		return
	}

	// Generate random MAC address
	macAddress := generateRandomMAC()

	// Create domain XML
	domainXML := fmt.Sprintf(`
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
		<clock offset='utc'/>
		<devices>
			<disk type='file' device='disk'>
				<driver name='qemu' type='qcow2'/>
				<source file='%s'/>
				<target dev='vda' bus='virtio'/>
			</disk>
			<disk type='file' device='cdrom'>
				<driver name='qemu' type='raw'/>
				<source file='%s'/>
				<target dev='hdc' bus='ide'/>
				<readonly/>
			</disk>
			<interface type='network'>
				<source network='%s'/>
				<mac address='%s'/>
				<model type='virtio'/>
			</interface>
			<console type='pty'/>
			<graphics type='vnc' port='-1' autoport='yes' listen='0.0.0.0'/>
			<channel type='unix'>
				<target type='virtio' name='org.qemu.guest_agent.0'/>
			</channel>
		</devices>
	</domain>`, vm.Name, diskPath, cloudInitISOPath, 
		m.networkName != "" ? m.networkName : "default", macAddress)

	// Define domain
	m.mutex.RLock()
	conn := m.conn
	m.mutex.RUnlock()

	domain, err := conn.DomainDefineXML(domainXML)
	if err != nil {
		m.setVMError(vm, fmt.Sprintf("Failed to define domain: %v", err))
		return
	}
	defer domain.Free()

	// Start domain
	if err := domain.Create(); err != nil {
		m.setVMError(vm, fmt.Sprintf("Failed to start domain: %v", err))
		return
	}

	m.logger.Printf("VM %s started, waiting for IP address", vm.Name)

	// Wait for VM to get an IP address
	ipAddress, err := m.waitForIPAddress(domain, 5*time.Minute)
	if err != nil {
		m.setVMError(vm, fmt.Sprintf("Failed to get IP address: %v", err))
		return
	}

	m.logger.Printf("VM %s has IP address: %s", vm.Name, ipAddress)

	// Set up ngrok tunnel if auth token is available
	var ngrokURL string
	if m.ngrokAuth != "" {
		var err error
		ngrokURL, err = m.setupNgrokTunnel(ipAddress, 22)
		if err != nil {
			m.logger.Printf("Warning: Failed to set up ngrok tunnel: %v", err)
		} else {
			m.logger.Printf("Established ngrok tunnel for VM %s: %s", vm.Name, ngrokURL)
		}
	}

	// Update VM state
	m.mutex.Lock()
	vm.State = VMStateRunning
	vm.IPAddress = ipAddress
	vm.NgrokURL = ngrokURL
	vm.UpdatedAt = time.Now()
	m.mutex.Unlock()

	// Save VM state
	if err := m.saveVM(vm); err != nil {
		m.logger.Printf("Warning: Failed to save VM state: %v", err)
	}

	m.logger.Printf("VM %s is now running (IP: %s, Ngrok: %s)", vm.Name, ipAddress, ngrokURL)
}

// simulateProvisionVM simulates VM provisioning for development/testing
func (m *VMManager) simulateProvisionVM(vm *VM) {
	m.logger.Printf("Simulating VM provision for %s", vm.Name)

	// Simulate VM creation delay
	time.Sleep(3 * time.Second)

	// Update VM state with simulated values
	m.mutex.Lock()
	vm.State = VMStateRunning
	vm.IPAddress = fmt.Sprintf("192.168.122.%d", 100+rand.Intn(100))
	vm.NgrokURL = fmt.Sprintf("tcp://0.tcp.ngrok.io:%d", 10000+rand.Intn(10000))
	vm.UpdatedAt = time.Now()
	m.mutex.Unlock()

	// Save VM state
	if err := m.saveVM(vm); err != nil {
		m.logger.Printf("Warning: Failed to save VM state: %v", err)
	}

	m.logger.Printf("Simulated VM %s is now running (IP: %s, Ngrok: %s)", 
		vm.Name, vm.IPAddress, vm.NgrokURL)
}

// cloneTemplateDisk creates a copy of the template disk
func (m *VMManager) cloneTemplateDisk(templatePath, diskPath string) error {
	m.logger.Printf("Cloning template disk from %s to %s", templatePath, diskPath)
	
	// Use qemu-img to create a backing file for efficiency
	cmd := exec.Command("qemu-img", "create", "-f", "qcow2", 
		"-F", "qcow2", "-b", templatePath, diskPath)
	
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("qemu-img failed: %w, output: %s", err, output)
	}
	
	return nil
}

// generateCloudInit creates a cloud-init ISO for VM configuration
func (m *VMManager) generateCloudInit(vm *VM, vmDir string) (string, error) {
	m.logger.Printf("Generating cloud-init configuration for VM %s", vm.Name)
	
	// Create cloud-init directory
	cloudInitDir := filepath.Join(vmDir, "cloud-init")
	if err := os.MkdirAll(cloudInitDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create cloud-init directory: %w", err)
	}
	
	// Create user-data
	userData := fmt.Sprintf(`#cloud-config
hostname: %s
users:
  - name: %s
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: sudo
    shell: /bin/bash
    lock_passwd: false
    passwd: %s
    
packages:
  - qemu-guest-agent
  - openssh-server
  - curl
  - wget
  - ca-certificates

runcmd:
  - systemctl enable qemu-guest-agent
  - systemctl start qemu-guest-agent
  - systemctl enable sshd
  - systemctl start sshd
`, vm.Name, vm.SSHUsername, vm.SSHPassword)

	// Create meta-data
	metaData := fmt.Sprintf(`instance-id: %s
local-hostname: %s
`, vm.ID, vm.Name)

	// Write files
	if err := os.WriteFile(filepath.Join(cloudInitDir, "user-data"), []byte(userData), 0644); err != nil {
		return "", fmt.Errorf("failed to write user-data: %w", err)
	}
	
	if err := os.WriteFile(filepath.Join(cloudInitDir, "meta-data"), []byte(metaData), 0644); err != nil {
		return "", fmt.Errorf("failed to write meta-data: %w", err)
	}
	
	// Generate ISO
	isoPath := filepath.Join(vmDir, "cloud-init.iso")
	cmd := exec.Command("genisoimage", "-output", isoPath, "-volid", "cidata", 
		"-joliet", "-rock", 
		filepath.Join(cloudInitDir, "user-data"),
		filepath.Join(cloudInitDir, "meta-data"))
	
	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("failed to generate cloud-init ISO: %w, output: %s", err, output)
	}
	
	return isoPath, nil
}

// waitForIPAddress waits for VM to get an IP address
func (m *VMManager) waitForIPAddress(domain *libvirt.Domain, timeout time.Duration) (string, error) {
	deadline := time.Now().Add(timeout)
	
	for time.Now().Before(deadline) {
		// Check if domain is running
		state, _, err := domain.GetState()
		if err != nil {
			return "", fmt.Errorf("failed to get domain state: %w", err)
		}
		
		if state != libvirt.DOMAIN_RUNNING {
			time.Sleep(1 * time.Second)
			continue
		}
		
		// First try: Use QEMU guest agent (most reliable)
		ifaces, err := domain.InterfaceAddresses(libvirt.DOMAIN_INTERFACE_ADDRESSES_SRC_AGENT, 0)
		if err == nil {
			for _, iface := range ifaces {
				for _, addr := range iface.Addrs {
					if addr.Type == libvirt.IP_ADDR_TYPE_IPV4 {
						return addr.Addr, nil
					}
				}
			}
		}
		
		// Second try: Use DHCP leases
		ifaces, err = domain.InterfaceAddresses(libvirt.DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE, 0)
		if err == nil {
			for _, iface := range ifaces {
				for _, addr := range iface.Addrs {
					if addr.Type == libvirt.IP_ADDR_TYPE_IPV4 {
						return addr.Addr, nil
					}
				}
			}
		}
		
		time.Sleep(2 * time.Second)
	}
	
	return "", fmt.Errorf("timeout waiting for IP address")
}

// setupNgrokTunnel sets up an ngrok tunnel for SSH access
func (m *VMManager) setupNgrokTunnel(ipAddress string, port int) (string, error) {
	// Check if ngrok auth token is set
	if m.ngrokAuth == "" {
		return "", fmt.Errorf("NGROK_AUTH_TOKEN not set")
	}
	
	// Set ngrok region
	region := m.ngrokRegion
	if region == "" {
		region = "us"
	}
	
	// Start ngrok tunnel
	m.logger.Printf("Setting up ngrok tunnel for %s:%d", ipAddress, port)
	
	target := fmt.Sprintf("%s:%d", ipAddress, port)
	cmd := exec.Command("ngrok", "tcp", "--region", region, target)
	cmd.Env = append(os.Environ(), fmt.Sprintf("NGROK_AUTHTOKEN=%s", m.ngrokAuth))
	
	if err := cmd.Start(); err != nil {
		return "", fmt.Errorf("failed to start ngrok: %w", err)
	}
	
	// Wait for tunnel to establish
	time.Sleep(3 * time.Second)
	
	// Query ngrok API for tunnel URL
	resp, err := http.Get("http://localhost:4040/api/tunnels")
	if err != nil {
		return "", fmt.Errorf("failed to query ngrok API: %w", err)
	}
	defer resp.Body.Close()
	
	var result struct {
		Tunnels []struct {
			PublicURL string `json:"public_url"`
			Proto     string `json:"proto"`
		} `json:"tunnels"`
	}
	
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("failed to parse ngrok API response: %w", err)
	}
	
	// Get TCP tunnel URL
	for _, tunnel := range result.Tunnels {
		if tunnel.Proto == "tcp" {
			return tunnel.PublicURL, nil
		}
	}
	
	return "", fmt.Errorf("no TCP tunnel found")
}

// GetVM retrieves VM information by ID
func (m *VMManager) GetVM(vmID string) (*VM, error) {
	m.mutex.RLock()
	defer m.mutex.RUnlock()
	
	vm, exists := m.vms[vmID]
	if !exists {
		return nil, fmt.Errorf("VM not found: %s", vmID)
	}
	
	// In simulation mode, just return the VM
	if m.simulation {
		return vm, nil
	}
	
	// Refresh VM state from libvirt if needed
	if vm.State == VMStateRunning || vm.State == VMStateStopped {
		domain, err := m.conn.LookupDomainByName(vm.Name)
		if err == nil {
			defer domain.Free()
			
			state, _, err := domain.GetState()
			if err == nil {
				var vmState string
				switch state {
				case libvirt.DOMAIN_RUNNING:
					vmState = VMStateRunning
				case libvirt.DOMAIN_SHUTOFF:
					vmState = VMStateStopped
				default:
					vmState = fmt.Sprintf("unknown(%d)", state)
				}
				
				if vm.State != vmState {
					vm.State = vmState
					vm.UpdatedAt = time.Now()
					// Save updated state asynchronously
					go m.saveVM(vm)
				}
			}
		}
	}
	
	return vm, nil
}

// GetVMByTask retrieves VM information by task ID
func (m *VMManager) GetVMByTask(taskID string) (*VM, error) {
	m.mutex.RLock()
	defer m.mutex.RUnlock()
	
	vmID, exists := m.taskToVMMap[taskID]
	if !exists {
		return nil, fmt.Errorf("no VM found for task: %s", taskID)
	}
	
	vm, exists := m.vms[vmID]
	if !exists {
		return nil, fmt.Errorf("VM not found: %s", vmID)
	}
	
	return vm, nil
}

// ListVMs lists all VMs
func (m *VMManager) ListVMs() []*VM {
	m.mutex.RLock()
	defer m.mutex.RUnlock()
	
	vms := make([]*VM, 0, len(m.vms))
	for _, vm := range m.vms {
		vms = append(vms, vm)
	}
	
	return vms
}

// DestroyVM destroys a VM
func (m *VMManager) DestroyVM(vmID string) error {
	m.mutex.Lock()
	
	vm, exists := m.vms[vmID]
	if !exists {
		m.mutex.Unlock()
		return fmt.Errorf("VM not found: %s", vmID)
	}
	
	// Update state to destroying
	vm.State = VMStateDestroying
	vm.UpdatedAt = time.Now()
	
	// Save state before unlocking
	if err := m.saveVM(vm); err != nil {
		m.logger.Printf("Warning: Failed to save VM state: %v", err)
	}
	
	m.mutex.Unlock()
	
	m.logger.Printf("Destroying VM %s", vm.Name)
	
	// In simulation mode, just simulate VM destruction
	if m.simulation {
		time.Sleep(2 * time.Second)
		
		m.mutex.Lock()
		delete(m.vms, vmID)
		if vm.TaskID != "" {
			delete(m.taskToVMMap, vm.TaskID)
		}
		m.mutex.Unlock()
		
		// Remove VM data file
		vmFile := filepath.Join(m.baseDir, "vm-data", fmt.Sprintf("%s.json", vmID))
		os.Remove(vmFile)
		
		return nil
	}
	
	// Get domain
	domain, err := m.conn.LookupDomainByName(vm.Name)
	if err != nil {
		m.logger.Printf("Warning: Failed to lookup domain: %v", err)
	} else {
		defer domain.Free()
		
		// Check domain state
		state, _, err := domain.GetState()
		if err == nil && state == libvirt.DOMAIN_RUNNING {
			// Try graceful shutdown first
			if err := domain.Shutdown(); err != nil {
				m.logger.Printf("Warning: Failed to shutdown domain gracefully: %v", err)
				
				// Force destroy
				if err := domain.Destroy(); err != nil {
					m.logger.Printf("Warning: Failed to destroy domain: %v", err)
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
		
		// Undefine domain with volumes
		if err := domain.Undefine(); err != nil {
			m.logger.Printf("Warning: Failed to undefine domain: %v", err)
		}
	}
	
	// Clean up VM files
	vmDir := filepath.Join(m.baseDir, "instances", vmID)
	if err := os.RemoveAll(vmDir); err != nil {
		m.logger.Printf("Warning: Failed to remove VM directory: %v", err)
	}
	
	// Remove VM from maps
	m.mutex.Lock()
	delete(m.vms, vmID)
	if vm.TaskID != "" {
		delete(m.taskToVMMap, vm.TaskID)
	}
	m.mutex.Unlock()
	
	// Remove VM data file
	vmFile := filepath.Join(m.baseDir, "vm-data", fmt.Sprintf("%s.json", vmID))
	if err := os.Remove(vmFile); err != nil && !os.IsNotExist(err) {
		m.logger.Printf("Warning: Failed to remove VM data file: %v", err)
	}
	
	m.logger.Printf("VM %s destroyed", vm.Name)
	
	return nil
}

// ResetVM resets a VM to clean state
func (m *VMManager) ResetVM(vmID string) error {
	m.mutex.Lock()
	
	vm, exists := m.vms[vmID]
	if !exists {
		m.mutex.Unlock()
		return fmt.Errorf("VM not found: %s", vmID)
	}
	
	taskID := vm.TaskID
	oldState := vm.State
	
	// Update state to resetting
	vm.State = VMStateResetting
	vm.UpdatedAt = time.Now()
	
	// Save state before unlocking
	if err := m.saveVM(vm); err != nil {
		m.logger.Printf("Warning: Failed to save VM state: %v", err)
	}
	
	m.mutex.Unlock()
	
	m.logger.Printf("Resetting VM %s from state %s", vm.Name, oldState)
	
	// In simulation mode, just simulate VM reset
	if m.simulation {
		time.Sleep(3 * time.Second)
		
		m.mutex.Lock()
		vm.State = VMStateRunning
		vm.UpdatedAt = time.Now()
		m.mutex.Unlock()
		
		// Save VM state
		if err := m.saveVM(vm); err != nil {
			m.logger.Printf("Warning: Failed to save VM state: %v", err)
		}
		
		return nil
	}
	
	// Destroy existing VM
	if err := m.DestroyVM(vmID); err != nil {
		return fmt.Errorf("failed to destroy VM: %w", err)
	}
	
	// Wait a moment for resources to be released
	time.Sleep(2 * time.Second)
	
	// Create a new VM with the same task ID
	_, err := m.CreateVM(taskID)
	if err != nil {
		return fmt.Errorf("failed to create new VM: %w", err)
	}
	
	return nil
}

// generateRandomMAC generates a random MAC address
func generateRandomMAC() string {
	buf := make([]byte, 6)
	if _, err := rand.Read(buf); err != nil {
		return "52:54:00:00:00:01" // Fallback
	}
	
	// Ensure it's a valid MAC for VMs (locally administered)
	buf[0] = (buf[0] & 0xfe) | 0x02
	
	return fmt.Sprintf("52:54:%02x:%02x:%02x:%02x", 
		buf[2], buf[3], buf[4], buf[5])
}

// generateRandomPassword generates a random password
func generateRandomPassword(length int) string {
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	buf := make([]byte, length)
	for i := range buf {
		buf[i] = charset[rand.Intn(len(charset))]
	}
	return string(buf)
}
