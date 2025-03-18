package main

import (
	"os"
	"path/filepath"
)

// Config holds the VM Manager configuration
type Config struct {
	LibvirtURI       string
	BaseDir          string
	TemplatePath     string
	NetworkName      string
	NgrokAuthToken   string
	NgrokRegion      string
	EnableSimulation bool
	ListenAddress    string
}

// LoadConfig loads configuration from environment variables
func LoadConfig() Config {
	// Get base directory
	baseDir := os.Getenv("VM_DATA_DIR")
	if baseDir == "" {
		baseDir = "/var/lib/linux-agent-system/vms"
	}

	// Create base directory if it doesn't exist
	os.MkdirAll(baseDir, 0755)

	// Get template path
	templatePath := os.Getenv("VM_TEMPLATE_PATH")
	if templatePath == "" {
		// Default to template in base directory
		templatePath = filepath.Join(baseDir, "templates", "opensuse-tumbleweed-template.qcow2")
	}

	// Get libvirt URI
	libvirtURI := os.Getenv("LIBVIRT_URI")
	if libvirtURI == "" {
		libvirtURI = "qemu:///system"
	}

	// Get network name
	networkName := os.Getenv("LIBVIRT_NETWORK")
	if networkName == "" {
		networkName = "default"
	}

	// Get ngrok configuration
	ngrokAuthToken := os.Getenv("NGROK_AUTH_TOKEN")
	ngrokRegion := os.Getenv("NGROK_REGION")
	if ngrokRegion == "" {
		ngrokRegion = "us"
	}

	// Check if simulation mode is enabled
	enableSimulation := os.Getenv("ENABLE_SIMULATION") == "true"

	// Get listen address
	listenAddress := os.Getenv("VM_MANAGER_PORT")
	if listenAddress == "" {
		listenAddress = "8083"
	}
	listenAddress = ":" + listenAddress

	return Config{
		LibvirtURI:       libvirtURI,
		BaseDir:          baseDir,
		TemplatePath:     templatePath,
		NetworkName:      networkName,
		NgrokAuthToken:   ngrokAuthToken,
		NgrokRegion:      ngrokRegion,
		EnableSimulation: enableSimulation,
		ListenAddress:    listenAddress,
	}
}
