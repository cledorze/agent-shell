use std::process::Command;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use serde::{Deserialize, Serialize};
use tiny_http::{Server, Response, Method, Header};

// Command request structure
#[derive(Deserialize)]
struct CommandRequest {
    command: String,
    args: Option<Vec<String>>,
    working_dir: Option<String>,
}

// Command response structure
#[derive(Serialize, Clone)]
struct CommandResponse {
    id: String,
    status: String,
    stdout: String,
    stderr: String,
    exit_code: i32,
}

fn main() {
    println!("Starting Command Executor service on port 8084");
    
    // Create a simple HTTP server
    let server = Server::http("0.0.0.0:8084").unwrap();
    
    // Create a shared state for storing command results
    let command_results: Arc<Mutex<HashMap<String, CommandResponse>>> = 
        Arc::new(Mutex::new(HashMap::new()));
    
    // Request counter to generate unique IDs
    let counter = Arc::new(Mutex::new(0));
    
    // Process each incoming request
    for mut request in server.incoming_requests() {
        // Get the URL and method before doing anything else
        let url = request.url().to_string();
        let method = request.method().clone();
        
        // Handle health check
        if url == "/health" && method == Method::Get {
            let _ = request.respond(Response::from_string("Command Executor service is healthy"));
            continue;
        }
        
        // Handle execute command
        if url == "/execute" && method == Method::Post {
            let mut content = String::new();
            if let Err(_) = request.as_reader().read_to_string(&mut content) {
                let _ = request.respond(Response::from_string("Failed to read request body").with_status_code(400));
                continue;
            }
            
            let command_req: CommandRequest = match serde_json::from_str(&content) {
                Ok(req) => req,
                Err(_) => {
                    let _ = request.respond(Response::from_string("Invalid JSON").with_status_code(400));
                    continue;
                }
            };
            
            // Build the command
            let mut cmd = Command::new(&command_req.command);
            
            // Add arguments if provided
            if let Some(args) = &command_req.args {
                cmd.args(args);
            }
            
            // Set working directory if provided
            if let Some(dir) = &command_req.working_dir {
                cmd.current_dir(dir);
            }
            
            // Generate command ID
            let cmd_id = {
                let mut count = counter.lock().unwrap();
                *count += 1;
                format!("cmd-{}", *count)
            };
            
            // Execute the command
            let output = match cmd.output() {
                Ok(output) => output,
                Err(e) => {
                    let response = CommandResponse {
                        id: cmd_id,
                        status: "error".to_string(),
                        stdout: "".to_string(),
                        stderr: format!("Failed to execute command: {}", e),
                        exit_code: -1,
                    };
                    
                    let json = serde_json::to_string(&response).unwrap();
                    let _ = request.respond(Response::from_string(json).with_status_code(500));
                    continue;
                }
            };
            
            // Process command output
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            let exit_code = output.status.code().unwrap_or(-1);
            
            let status = if output.status.success() {
                "success"
            } else {
                "failed"
            };
            
            // Create response
            let response = CommandResponse {
                id: cmd_id.clone(),
                status: status.to_string(),
                stdout,
                stderr,
                exit_code,
            };
            
            // Store the result
            command_results.lock().unwrap().insert(cmd_id, response.clone());
            
            // Send response
            let json = serde_json::to_string(&response).unwrap();
            
            // Create a proper header object directly
            let content_type = Header::from_bytes("Content-Type", "application/json").unwrap();
            
            let _ = request.respond(Response::from_string(json).with_header(content_type));
            continue;
        }
        
        // Handle results retrieval
        if url.starts_with("/results/") && method == Method::Get {
            // Extract the command ID from the URL
            let cmd_id = url.trim_start_matches("/results/").to_string();
            
            // Get result from storage
            let result = command_results.lock().unwrap().get(&cmd_id).cloned();
            
            match result {
                Some(response) => {
                    let json = serde_json::to_string(&response).unwrap();
                    let content_type = Header::from_bytes("Content-Type", "application/json").unwrap();
                    let _ = request.respond(Response::from_string(json).with_header(content_type));
                }
                None => {
                    let error_msg = format!("Command result with ID {} not found", cmd_id);
                    let _ = request.respond(Response::from_string(error_msg).with_status_code(404));
                }
            }
            continue;
        }
        
        // Handle unknown request
        let _ = request.respond(Response::from_string("Not found").with_status_code(404));
    }
}
