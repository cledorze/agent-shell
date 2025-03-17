use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use tokio::process::Command;
use tower_http::trace::TraceLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};
use std::collections::HashMap;
use uuid::Uuid;
use std::time::{Duration, Instant};
use tower_http::cors::{Any, CorsLayer};
use chrono::Utc;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct CommandRequest {
    command: String,
    timeout_seconds: Option<u64>,
    working_directory: Option<String>,
    environment: Option<HashMap<String, String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct CommandResult {
    id: String,
    command: String,
    status: CommandStatus,
    stdout: Option<String>,
    stderr: Option<String>,
    exit_code: Option<i32>,
    execution_time_ms: Option<u64>,
    created_at: chrono::DateTime<chrono::Utc>,
    completed_at: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
enum CommandStatus {
    Pending,
    Running,
    Completed,
    Failed,
    TimedOut,
}

struct AppState {
    command_results: Mutex<HashMap<String, CommandResult>>,
}

#[tokio::main]
async fn main() {
    // Initialize logging
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into()),
        ))
        .with(tracing_subscriber::fmt::layer())
        .init();

    // CORS configuration
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    // Create shared state
    let state = Arc::new(AppState {
        command_results: Mutex::new(HashMap::new()),
    });

    // Define routes
    let app = Router::new()
        .route("/", get(|| async { "Command Executor API" }))
        .route("/health", get(health_check))
        .route("/execute", post(execute_command))
        .route("/result/:id", get(get_command_result))
        .layer(TraceLayer::new_for_http())
        .layer(cors)
        .with_state(Arc::clone(&state));

    // Start server
    let port = std::env::var("COMMAND_EXECUTOR_PORT").unwrap_or_else(|_| "8085".to_string());
    let addr = format!("0.0.0.0:{}", port).parse().unwrap();
    tracing::info!("Command Executor listening on {}", addr);
    
    axum::Server::bind(&addr)
        .serve(app.into_make_service())
        .await
        .unwrap();
}

async fn health_check() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "status": "healthy",
        "version": env!("CARGO_PKG_VERSION")
    }))
}

async fn execute_command(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CommandRequest>,
) -> Result<Json<CommandResult>, (StatusCode, String)> {
    // Command validation and sanitization
    if request.command.trim().is_empty() {
        return Err((StatusCode::BAD_REQUEST, "Command cannot be empty".to_string()));
    }

    // Check if command is blacklisted (example)
    let blacklisted_commands = vec!["rm -rf /", "mkfs", "dd if=/dev/zero"];
    for cmd in blacklisted_commands {
        if request.command.contains(cmd) {
            return Err((
                StatusCode::FORBIDDEN,
                "Command contains disallowed operations".to_string(),
            ));
        }
    }

    // Create ID for this execution
    let id = Uuid::new_v4().to_string();
    
    // Register command as pending
    let command_result = CommandResult {
        id: id.clone(),
        command: request.command.clone(),
        status: CommandStatus::Pending,
        stdout: None,
        stderr: None,
        exit_code: None,
        execution_time_ms: None,
        created_at: Utc::now(),
        completed_at: None,
    };
    
    {
        let mut results = state.command_results.lock().
