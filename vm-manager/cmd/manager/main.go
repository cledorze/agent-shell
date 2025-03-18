package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gorilla/mux"
	"github.com/user/linux-agent-system/vm-manager/internal/libvirt"
)

func main() {
	// Set up logging
	logger := log.New(os.Stdout, "[VM Manager] ", log.LstdFlags)
	logger.Println("Starting VM Manager")

	// Load configuration
	config := LoadConfig()
	logger.Printf("Configuration loaded: %+v", config)

	// Initialize VM manager
	vmManagerConfig := libvirt.Config{
		LibvirtURI:       config.LibvirtURI,
		BaseDir:          config.BaseDir,
		TemplatePath:     config.TemplatePath,
		NetworkName:      config.NetworkName,
		NgrokAuthToken:   config.NgrokAuthToken,
		NgrokRegion:      config.NgrokRegion,
		EnableSimulation: config.EnableSimulation,
	}

	vmManager, err := libvirt.NewVMManager(vmManagerConfig)
	if err != nil {
		logger.Fatalf("Failed to initialize VM manager: %v", err)
	}
	defer vmManager.Close()

	// Set up HTTP server
	r := mux.NewRouter()
	
	// Set up handlers
	handler := NewHTTPHandler(vmManager, logger)
	handler.SetupRoutes(r)

	// Configure the HTTP server
	server := &http.Server{
		Addr:         config.ListenAddress,
		Handler:      r,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start the server in a goroutine
	go func() {
		logger.Printf("Server listening on %s", config.ListenAddress)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatalf("Failed to start server: %v", err)
		}
	}()

	// Set up graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	// Shutdown the server
	logger.Println("Shutting down server...")
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		logger.Fatalf("Server forced to shutdown: %v", err)
	}

	logger.Println("Server exited properly")
}
