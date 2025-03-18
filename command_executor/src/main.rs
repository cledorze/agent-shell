use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use serde::{Deserialize, Serialize};
use std::process::Command;

#[derive(Debug, Deserialize)]
struct CommandRequest {
    command: String,
}

#[derive(Debug, Serialize)]
struct CommandResponse {
    status: String,
    stdout: String,
    stderr: String,
    exit_code: i32,
}

async fn health_check() -> impl Responder {
    HttpResponse::Ok().body("Command Executor service is healthy")
}

async fn execute_command(command_req: web::Json<CommandRequest>) -> impl Responder {
    let output = Command::new("sh")
        .arg("-c")
        .arg(&command_req.command)
        .output();

    match output {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            let exit_code = output.status.code().unwrap_or(-1);
            
            let status = if output.status.success() {
                "success"
            } else {
                "failed"
            };
            
            HttpResponse::Ok().json(CommandResponse {
                status: status.to_string(),
                stdout,
                stderr,
                exit_code,
            })
        },
        Err(e) => {
            HttpResponse::InternalServerError().json(CommandResponse {
                status: "error".to_string(),
                stdout: "".to_string(),
                stderr: format!("Failed to execute command: {}", e),
                exit_code: -1,
            })
        }
    }
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    println!("Starting Command Executor service on port 8084");
    
    HttpServer::new(|| {
        App::new()
            .route("/health", web::get().to(health_check))
            .route("/execute", web::post().to(execute_command))
    })
    .bind("0.0.0.0:8084")?
    .run()
    .await
}
