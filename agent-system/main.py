from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

# Import configuration and components
from config import initialize_components, setup_logging, frontend_dir
from routes import router  # This is now correct with our bridge file

# Configure logging
logger = setup_logging()

# Initialize components
command_generator, execution_engine, state_manager, llm_service = initialize_components()

# Initialize FastAPI application
app = FastAPI(title="Linux Agent System")

# Mount static files for frontend if they exist
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    logger.info(f"Mounted frontend directory: {frontend_dir}")

# Add routes
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8082, reload=True)
