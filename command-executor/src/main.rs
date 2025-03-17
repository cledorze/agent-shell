// command-executor/src/main.rs
use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::process::Stdio;
use std::sync::{Arc, Mutex};
use tokio::process::Command;
use tokio::time::{sleep, Duration, Instant};
use tower_http::cors::{Any, CorsLayer};
use tower_http::trace::TraceLayer;
use tracing::{debug, error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};
use uuid::Uuid;
use reqwest::Client;
use chrono::{DateTime, Utc};
use dotenv::dotenv;

// Command request model
#[derive(Debug, Clone, Serialize, Deserialize)]
struct CommandRequest {
    command: String,
    task_id: Option<String>,
    vm_id: Option<String>,
    timeout_seconds: Option<u64>,
    working_directory: Option<String>,
    environment: Option<HashMap<String, String>>,
}

// Command result model
#[derive(Debug, Clone, Serialize, Deserialize)]
struct CommandResult {
    id: String,
    task_id: Option<String>,
    vm_id: Option<String>,
    command: String,
    status: CommandStatus,
    stdout: Option<String>,
    stderr: Option<String>,
    exit_code: Option<i32>,
    execution_time_ms: Option<u64>,
    created_at: DateTime<Utc>,
    completed_at: Option<DateTime<Utc>>,
    vm_details: Option<VmDetails>,
}

// VM details model
#[derive(Debug, Clone, Serialize, Deserialize)]
struct VmDetails {
    id: String,
    name: String,
    state: String,
    ip_address: Option<String>,
    ngrok_url: Option<String>,
    ssh_username: Option<String>,
    ssh_password: Option<String>,
}

// Command status enum
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
enum CommandStatus {
    Pending,
    Running,
    Completed,
    Failed,
    TimedOut,
}

// Ngrok tunnel info
#[derive(Debug, Clone, Serialize, Deserialize)]
struct NgrokTunnel {
    name: String,
    uri: String,
    public_url: String,
    proto: String,
    #[serde(rename = "config")]
    tunnel_config: NgrokTunnelConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct NgrokTunnelConfig {
    addr: String,
    inspect: bool,
}

// VM Manager response
#[derive(Debug, Clone, Serialize, Deserialize)]
struct VmResponse {
    id: String,
    name: String,
    state: String,
    ip_address: Option<String>,
    ngrok_url: Option<String>,
    task_id: Option<String>,
    ssh_username: String,
    ssh_password: String,
}

// App state
struct AppState {
    command_results: Mutex<HashMap<String, CommandResult>>,
    http_client: Client,
    vm_manager_url: String,
    ngrok_auth_token: String,
}

// Main function
#[tokio::main]
async fn main() {
    // Load environment variables
    dotenv().ok();

    // Initialize logging
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into()),
        ))
        .with(tracing_subscriber::fmt::layer())
        .init();

    // Get configuration from environment
    let port = std::env::var("COMMAND_EXECUTOR_PORT").unwrap_or_else(|_| "8085".to_string());
    let vm_manager_url = std::env::var("VM_MANAGER_URL")
        .unwrap_or_else(|_| "http://vm-manager:8083".to_string());
    let ngrok_auth_token = std::env::var("NGROK_AUTH_TOKEN")
        .unwrap_or_else(|_| {
            warn!("NGROK_AUTH_TOKEN not set. Command execution on VMs will be limited.");
            "".to_string()
        });

    // Create HTTP client
    let http_client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .expect("Failed to create HTTP client");

    // CORS configuration
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    // Create shared state
    let state = Arc::new(AppState {
        command_results: Mutex::new(HashMap::new()),
        http_client,
        vm_manager_url,
        ngrok_auth_token,
    });

    // Define routes
    let app = Router::new()
        .route("/", get(|| async { "Command Executor API" }))
        .route("/health", get(health_check))
        .route("/execute", post(execute_command))
        .route("/execute/vm", post(execute_command_on_vm))
        .route("/result/:id", get(get_command_result))
        .layer(TraceLayer::new_for_http())
        .layer(cors)
        .with_state(Arc::clone(&state));

    // Start server
    let addr = format!("0.0.0.0:{}", port).parse().unwrap();
    info!("Command Executor listening on {}", addr);
    
    axum::Server::bind(&addr)
        .serve(app.into_make_service())
        .await
        .unwrap();
}

// Health check handler
async fn health_check(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let command_count = state.command_results.lock().unwrap().len();
    
    Json(serde_json::json!({
        "status": "healthy",
        "version": env!("CARGO_PKG_VERSION"),
        "vm_manager_url": state.vm_manager_url,
        "has_ngrok_token": !state.ngrok_auth_token.is_empty(),
        "command_count": command_count
    }))
}

// Execute command handler (local execution)
async fn execute_command(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CommandRequest>,
) -> Result<Json<CommandResult>, (StatusCode, String)> {
    // Command validation
    if request.command.trim().is_empty() {
        return Err((StatusCode::BAD_REQUEST, "Command cannot be empty".to_string()));
    }

    // Create ID for this execution
    let id = Uuid::new_v4().to_string();
    
    // Register command as pending
    let command_result = CommandResult {
        id: id.clone(),
        task_id: request.task_id.clone(),
        vm_id: request.vm_id.clone(),
        command: request.command.clone(),
        status: CommandStatus::Pending,
        stdout: None,
        stderr: None,
        exit_code: None,
        execution_time_ms: None,
        created_at: Utc::now(),
        completed_at: None,
        vm_details: None,
    };
    
    {
        let mut results = state.command_results.lock().unwrap();
        results.insert(id.clone(), command_result.clone());
    }
    
    // Execute command in background
    tokio::spawn(execute_command_task(
        state.clone(),
        id.clone(),
        request,
    ));
    
    // Return the pending result
    Ok(Json(command_result))
}

// Execute command on VM handler
async fn execute_command_on_vm(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CommandRequest>,
) -> Result<Json<CommandResult>, (StatusCode, String)> {
    // Command validation
    if request.command.trim().is_empty() {
        return Err((StatusCode::BAD_REQUEST, "Command cannot be empty".to_string()));
    }

    // Task ID or VM ID is required
    if request.task_id.is_none() && request.vm_id.is_none() {
        return Err((StatusCode::BAD_REQUEST, "Either task_id or vm_id is required".to_string()));
    }

    // Create ID for this execution
    let id = Uuid::new_v4().to_string();
    
    // Register command as pending
    let command_result = CommandResult {
        id: id.clone(),
        task_id: request.task_id.clone(),
        vm_id: request.vm_id.clone(),
        command: request.command.clone(),
        status: CommandStatus::Pending,
        stdout: None,
        stderr: None,
        exit_code: None,
        execution_time_ms: None,
        created_at: Utc::now(),
        completed_at: None,
        vm_details: None,
    };
    
    {
        let mut results = state.command_results.lock().unwrap();
        results.insert(id.clone(), command_result.clone());
    }
    
    // Execute command in background
    tokio::spawn(execute_command_on_vm_task(
        state.clone(),
        id.clone(),
        request,
    ));
    
    // Return the pending result
    Ok(Json(command_result))
}

// Get command result handler
async fn get_command_result(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<CommandResult>, (StatusCode, String)> {
    let results = state.command_results.lock().unwrap();
    
    match results.get(&id) {
        Some(result) => Ok(Json(result.clone())),
        None => Err((StatusCode::NOT_FOUND, "Command result not found".to_string())),
    }
}

// Background task for local command execution
async fn execute_command_task(
    state: Arc<AppState>,
    id: String,
    request: CommandRequest,
) {
    let timeout = request.timeout_seconds.unwrap_or(60);
    let start_time = Instant::now();
    
    // Update status to running
    {
        let mut results = state.command_results.lock().unwrap();
        if let Some(result) = results.get_mut(&id) {
            result.status = CommandStatus::Running;
        }
    }
    
    // Build command
    let mut cmd = Command::new("sh");
    cmd.arg("-c").arg(&request.command);
    
    // Set working directory if specified
    if let Some(dir) = &request.working_directory {
        cmd.current_dir(dir);
    }
    
    // Set environment variables if specified
    if let Some(env) = &request.environment {
        for (key, value) in env {
            cmd.env(key, value);
        }
    }
    
    // Configure stdio
    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());
    
    // Execute command with timeout
    info!("Executing command: {}", request.command);
    let result = tokio::time::timeout(Duration::from_secs(timeout), cmd.spawn().unwrap().wait_with_output()).await;
    
    // Process result
    let execution_time = start_time.elapsed();
    let status;
    let stdout;
    let stderr;
    let exit_code;
    
    match result {
        Ok(Ok(output)) => {
            stdout = Some(String::from_utf8_lossy(&output.stdout).to_string());
            stderr = Some(String::from_utf8_lossy(&output.stderr).to_string());
            exit_code = output.status.code();
            status = if output.status.success() {
                CommandStatus::Completed
            } else {
                CommandStatus::Failed
            };
            
            info!(
                "Command completed with exit code {:?} in {:?}",
                exit_code, execution_time
            );
        }
        Ok(Err(e)) => {
            stdout = None;
            stderr = Some(format!("Failed to execute command: {}", e));
            exit_code = Some(-1);
            status = CommandStatus::Failed;
            
            error!("Command execution error: {}", e);
        }
        Err(_) => {
            stdout = None;
            stderr = Some(format!("Command timed out after {} seconds", timeout));
            exit_code = Some(-1);
            status = CommandStatus::TimedOut;
            
            warn!("Command timed out after {} seconds", timeout);
        }
    }
    
    // Update command result
    {
        let mut results = state.command_results.lock().unwrap();
        if let Some(result) = results.get_mut(&id) {
            result.status = status;
            result.stdout = stdout;
            result.stderr = stderr;
            result.exit_code = exit_code;
            result.execution_time_ms = Some(execution_time.as_millis() as u64);
            result.completed_at = Some(Utc::now());
        }
    }
}

// Background task for VM command execution
async fn execute_command_on_vm_task(
    state: Arc<AppState>,
    id: String,
    request: CommandRequest,
) {
    let timeout = request.timeout_seconds.unwrap_or(60);
    let start_time = Instant::now();
    
    // Update status to running
    {
        let mut results = state.command_results.lock().unwrap();
        if let Some(result) = results.get_mut(&id) {
            result.status = CommandStatus::Running;
        }
    }
    
    // Get VM details from VM Manager
    let vm_details = match get_vm_details(&state, &request).await {
        Ok(details) => details,
        Err(e) => {
            error!("Failed to get VM details: {}", e);
            
            // Update command result with error
            {
                let mut results = state.command_results.lock().unwrap();
                if let Some(result) = results.get_mut(&id) {
                    result.status = CommandStatus::Failed;
                    result.stderr = Some(format!("Failed to get VM details: {}", e));
                    result.exit_code = Some(-1);
                    result.execution_time_ms = Some(start_time.elapsed().as_millis() as u64);
                    result.completed_at = Some(Utc::now());
                }
            }
            
            return;
        }
    };
    
    // Update VM details in command result
    {
        let mut results = state.command_results.lock().unwrap();
        if let Some(result) = results.get_mut(&id) {
            result.vm_id = Some(vm_details.id.clone());
            result.vm_details = Some(vm_details.clone());
        }
    }
    
    // Check if VM is running
    if vm_details.state.to_lowercase() != "running" {
        error!("VM is not running: {}", vm_details.state);
        
        // Update command result with error
        {
            let mut results = state.command_results.lock().unwrap();
            if let Some(result) = results.get_mut(&id) {
                result.status = CommandStatus::Failed;
                result.stderr = Some(format!("VM is not running: {}", vm_details.state));
                result.exit_code = Some(-1);
                result.execution_time_ms = Some(start_time.elapsed().as_millis() as u64);
                result.completed_at = Some(Utc::now());
            }
        }
        
        return;
    }
    
    // Check if ngrok URL is available
    if vm_details.ngrok_url.is_none() {
        error!("VM does not have an ngrok URL");
        
        // Update command result with error
        {
            let mut results = state.command_results.lock().unwrap();
            if let Some(result) = results.get_mut(&id) {
                result.status = CommandStatus::Failed;
                result.stderr = Some("VM does not have an ngrok URL".to_string());
                result.exit_code = Some(-1);
                result.execution_time_ms = Some(start_time.elapsed().as_millis() as u64);
                result.completed_at = Some(Utc::now());
            }
        }
        
        return;
    }
    
    // Execute command on VM via SSH over ngrok
    info!("Executing command on VM {}: {}", vm_details.id, request.command);
    
    // Build SSH command
    let ssh_command = format!(
        "sshpass -p '{}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {} {}",
        vm_details.ssh_password.as_ref().unwrap_or(&"".to_string()),
        vm_details.ssh_username.as_ref().unwrap_or(&"agent".to_string()),
        vm_details.ngrok_url.as_ref().unwrap()
    );
    
    // Build the final command
    let command = format!("{} '{}'", ssh_command, request.command);
    
    // Execute SSH command
    let mut cmd = Command::new("sh");
    cmd.arg("-c").arg(&command);
    
    // Configure stdio
    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());
    
    // Execute command with timeout
    let result = tokio::time::timeout(Duration::from_secs(timeout), cmd.spawn().unwrap().wait_with_output()).await;
    
    // Process result
    let execution_time = start_time.elapsed();
    let status;
    let stdout;
    let stderr;
    let exit_code;
    
    match result {
        Ok(Ok(output)) => {
            stdout = Some(String::from_utf8_lossy(&output.stdout).to_string());
            stderr = Some(String::from_utf8_lossy(&output.stderr).to_string());
            exit_code = output.status.code();
            status = if output.status.success() {
                CommandStatus::Completed
            } else {
                CommandStatus::Failed
            };
            
            info!(
                "VM command completed with exit code {:?} in {:?}",
                exit_code, execution_time
            );
        }
        Ok(Err(e)) => {
            stdout = None;
            stderr = Some(format!("Failed to execute command on VM: {}", e));
            exit_code = Some(-1);
            status = CommandStatus::Failed;
            
            error!("VM command execution error: {}", e);
        }
        Err(_) => {
            stdout = None;
            stderr = Some(format!("Command on VM timed out after {} seconds", timeout));
            exit_code = Some(-1);
            status = CommandStatus::TimedOut;
            
            warn!("VM command timed out after {} seconds", timeout);
        }
    }
    
    // Update command result
    {
        let mut results = state.command_results.lock().unwrap();
        if let Some(result) = results.get_mut(&id) {
            result.status = status;
            result.stdout = stdout;
            result.stderr = stderr;
            result.exit_code = exit_code;
            result.execution_time_ms = Some(execution_time.as_millis() as u64);
            result.completed_at = Some(Utc::now());
        }
    }
}

// Helper function to get VM details
async fn get_vm_details(state: &Arc<AppState>, request: &CommandRequest) -> Result<VmDetails, String> {
    let client = &state.http_client;
    let vm_manager_url = &state.vm_manager_url;
    
    let url = if let Some(vm_id) = &request.vm_id {
        format!("{}/vms/{}", vm_manager_url, vm_id)
    } else if let Some(task_id) = &request.task_id {
        format!("{}/tasks/{}/vm", vm_manager_url, task_id)
    } else {
        return Err("Either task_id or vm_id is required".to_string());
    };
    
    match client.get(&url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<VmResponse>().await {
                    Ok(vm) => {
                        // Convert to VmDetails
                        Ok(VmDetails {
                            id: vm.id,
                            name: vm.name,
                            state: vm.state,
                            ip_address: vm.ip_address,
                            ngrok_url: vm.ngrok_url,
                            ssh_username: Some(vm.ssh_username),
                            ssh_password: Some(vm.ssh_password),
                        })
                    }
                    Err(e) => Err(format!("Failed to parse VM response: {}", e)),
                }
            } else {
                Err(format!("VM Manager returned error: {}", response.status()))
            }
        }
        Err(e) => Err(format!("Failed to connect to VM Manager: {}", e)),
    }
}
