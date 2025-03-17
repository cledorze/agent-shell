from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os

# Import configuration and components
from config import initialize_components, setup_logging, frontend_dir
from api.ui_handler import serve_frontend

# Configure logging
logger = setup_logging()

# Initialize components
command_generator, execution_engine, state_manager, llm_service = initialize_components()

# Initialize FastAPI application
app = FastAPI(title="Linux Agent System")

# Import the fixed task routes
from fixed_task_routes import router as task_router

# Add main UI route
@app.get("/", response_class=HTMLResponse)
async def root():
    return serve_frontend()

# Add health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "components": {
            "api": "healthy",
            "vm_manager": "unhealthy",
            "knowledge_system": "healthy",
            "command_executor": "unhealthy",
            "state_manager": "healthy",
            "execution_engine": "healthy",
            "command_generator": "healthy",
            "llm_service": "missing API key" if not llm_service.api_key else "healthy"
        }
    }

# Include task routes
app.include_router(task_router)

# Mount static files for frontend if they exist
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    logger.info(f"Mounted frontend directory: {frontend_dir}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8082, reload=True)
