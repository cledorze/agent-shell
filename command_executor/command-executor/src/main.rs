use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use serde::{Deserialize, Serialize};
use std::process::Command;
use log::{info, error};
use uuid::Uuid;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

// Command request structure
#[derive(Debug, Deserialize)]
struct CommandRequest {
    command: String,
    args: Option<Vec<String>>,
    working_dir: Option<String>,
}

// Command response structure
#[derive(Debug, Serialize)]
struct CommandResponse {
    id: String,
    status: String,
    stdout: String,
    stderr: String,
    exit_code: i32,
}

// In-memory storage for command results
struct AppState {
    command_results: Mutex<HashMap<String, CommandResponse>>,
}

async fn health_check() -> impl Responder {
    HttpResponse::Ok().body("Command Executor service is healthy")
}

async fn execute_command(
    data: web::Data<Arc<AppState>>,
    command_req: web::Json<CommandRequest>,
) -> impl Responder {
    let cmd_id = Uuid::new_v4().to_string();
    
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
    
    info!("Executing command: {:?}", cmd);
    
    // Execute the command
    let output = match cmd.output() {
        Ok(output) => output,
        Err(e) => {
            error!("Failed to execute command: {}", e);
            return HttpResponse::InternalServerError().json(CommandResponse {
                id: cmd_id,
                status: "error".to_string(),
                stdout: "".to_string(),
                stderr: format!("Failed to execute command: {}", e),
                exit_code: -1,
            });
        }
    };
    
    // Convert output to string
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
    data.command_results.lock().unwrap().insert(cmd_id.clone(), response.clone());
    
    HttpResponse::Ok().json(response)
}

async fn get_command_result(
    data: web::Data<Arc<AppState>>,
    path: web::Path<String>,
) -> impl Responder {
    let cmd_id = path.into_inner();
    
    // Get result from storage
    let result = data.command_results.lock().unwrap().get(&cmd_id).cloned();
    
    match result {
        Some(response) => HttpResponse::Ok().json(response),
        None => HttpResponse::NotFound().body(format!("Command result with ID {} not found", cmd_id)),
    }
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    env_logger::init_from_env(env_logger::Env::default().default_filter_or("info"));
    
    let app_data = Arc::new(AppState {
        command_results: Mutex::new(HashMap::new()),
    });
    
    info!("Starting Command Executor service on port 8084");
    
    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(app_data.clone()))
            .route("/health", web::get().to(health_check))
            .route("/execute", web::post().to(execute_command))
            .route("/results/{id}", web::get().to(get_command_result))
    })
    .bind("0.0.0.0:8084")?
    .run()
    .await
}
