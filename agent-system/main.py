from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import os
import uuid
import requests
import json
from datetime import datetime

# Import our custom modules
from agents.enhanced_command_generator import EnhancedCommandGenerator
from agents.execution_engine import ExecutionEngine
from utils.state_manager import StateManager
from utils.llm_service import LLMService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Linux Agent System")

# Configuration from environment variables
KNOWLEDGE_SYSTEM_URL = os.environ.get('KNOWLEDGE_SYSTEM_URL', 'http://knowledge-system:8084')
DATA_DIR = os.environ.get('DATA_DIR', '/app/data')
DRY_RUN = os.environ.get('DRY_RUN', 'true').lower() == 'true'
COMMAND_TIMEOUT = int(os.environ.get('COMMAND_TIMEOUT', '60'))
DEBUG_LEVEL = os.environ.get('DEBUG_LEVEL', 'INFO').upper()

# Set logging level based on configuration
logging.getLogger().setLevel(getattr(logging, DEBUG_LEVEL))

# Initialize our components
command_generator = EnhancedCommandGenerator(knowledge_system_url=KNOWLEDGE_SYSTEM_URL)
execution_engine = ExecutionEngine(dry_run=DRY_RUN, timeout=COMMAND_TIMEOUT)
state_manager = StateManager(state_dir=os.path.join(DATA_DIR, 'states'))
llm_service = LLMService(api_key=os.environ.get('OPENAI_API_KEY'))

# Define Pydantic models for request and response validation
class TaskRequest(BaseModel):
    task: str
    priority: Optional[str] = "normal"
    timeout: Optional[int] = 300
    execute: Optional[bool] = False

class TaskStatus(BaseModel):
    request_id: str
    status: str
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the frontend HTML directly without reading from a file."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Linux Agent System</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 800px; margin: 0 auto; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; }
            input[type="text"] { width: 100%; padding: 8px; }
            button { padding: 10px 15px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }
            .result { margin-top: 20px; padding: 15px; background-color: #f5f5f5; border-radius: 5px; }
            pre { white-space: pre-wrap; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Linux Agent System</h1>
            
            <div class="form-group">
                <label for="task">Enter a task:</label>
                <input type="text" id="task" placeholder="e.g., Check system memory usage">
            </div>
            
            <div class="form-group">
                <label>
                    <input type="checkbox" id="execute"> Execute commands (caution: this will run commands on the server)
                </label>
            </div>
            
            <button onclick="submitTask()">Submit Task</button>
            
            <div id="result" class="result" style="display: none;">
                <h3>Task Result:</h3>
                <pre id="resultContent"></pre>
            </div>
        </div>
        
        <script>
            function submitTask() {
                const task = document.getElementById('task').value;
                const execute = document.getElementById('execute').checked;
                
                if (!task) {
                    alert('Please enter a task');
                    return;
                }
                
                // Show loading indicator
                const resultDiv = document.getElementById('result');
                resultDiv.style.display = 'block';
                document.getElementById('resultContent').textContent = 'Processing...';
                
                // Submit the task
                fetch('/tasks', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        task: task,
                        execute: execute
                    })
                })
                .then(response => response.json())
                .then(data => {
                    // Display the result
                    document.getElementById('resultContent').textContent = JSON.stringify(data, null, 2);
                    
                    // If we have a request_id, poll for updates
                    if (data.request_id) {
                        pollTaskStatus(data.request_id);
                    }
                })
                .catch(error => {
                    document.getElementById('resultContent').textContent = 'Error: ' + error;
                });
            }
            
            function pollTaskStatus(requestId) {
                // Poll the task status every 2 seconds
                const interval = setInterval(() => {
                    fetch('/tasks/' + requestId)
                    .then(response => response.json())
                    .then(data => {
                        // Update the result
                        document.getElementById('resultContent').textContent = JSON.stringify(data, null, 2);
                        
                        // Stop polling if the task is completed or failed
                        if (data.status === 'completed' || data.status === 'failed') {
                            clearInterval(interval);
                        }
                    })
                    .catch(error => {
                        document.getElementById('resultContent').textContent = 'Error polling status: ' + error;
                        clearInterval(interval);
                    });
                }, 2000);
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check knowledge system connectivity
    try:
        response = requests.get(f"{KNOWLEDGE_SYSTEM_URL}/health", timeout=5)
        knowledge_system_healthy = response.status_code == 200
    except:
        knowledge_system_healthy = False
    
    return {
        "status": "healthy",
        "components": {
            "api": "healthy",
            "knowledge_system": "healthy" if knowledge_system_healthy else "unhealthy",
            "state_manager": "healthy",
            "execution_engine": "healthy",
            "command_generator": "healthy",
            "llm_service": "healthy" if llm_service.api_key else "missing API key"
        },
        "config": {
            "dry_run": DRY_RUN,
            "command_timeout": COMMAND_TIMEOUT,
            "debug_level": DEBUG_LEVEL
        }
    }

@app.post("/tasks", response_model=TaskStatus)
async def create_task(task_request: TaskRequest, background_tasks: BackgroundTasks):
    """Create a new task and start processing it."""
    # Generate a unique request ID
    request_id = str(uuid.uuid4())
    
    # Log the task
    logger.info(f"Received task: {task_request.task}")
    
    # Create execution state
    state = state_manager.create_state(request_id, task_request.task)
    
    # Start processing in the background
    background_tasks.add_task(
        process_task,
        task_id=request_id,
        task=task_request.task,
        execute=task_request.execute
    )
    
    # Return status
    return {
        "request_id": request_id,
        "status": "accepted",
        "message": "Task has been accepted and is being processed",
        "details": {"estimated_completion_time": task_request.timeout}
    }

@app.get("/tasks/{request_id}", response_model=TaskStatus)
async def get_task_status(request_id: str):
    """Get the status of a specific task."""
    state = state_manager.get_state(request_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Convert state to response format
    response = {
        "request_id": request_id,
        "status": state.status,
        "message": None,
        "details": {
            "current_step": state.current_step,
            "total_steps": state.total_steps,
            "start_time": state.start_time,
            "end_time": state.end_time,
            "executed_commands": state.executed_commands,
        }
    }
    
    # Add command outputs if available
    if state.command_outputs:
        response["details"]["command_outputs"] = state.command_outputs
    
    # Add execution plan if available
    if state.execution_plan:
        response["details"]["execution_plan"] = state.execution_plan
    
    # Add adaptations if available
    if state.adaptations:
        response["details"]["adaptations"] = state.adaptations
    
    return response

@app.get("/tasks/{request_id}/commands")
async def get_task_commands(request_id: str):
    """Get the commands for a specific task."""
    state = state_manager.get_state(request_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Extract commands from execution plan
    commands = []
    if state.execution_plan and "steps" in state.execution_plan:
        for step in state.execution_plan["steps"]:
            if "commands" in step:
                commands.extend(step["commands"])
    
    return {
        "request_id": request_id,
        "task": state.task,
        "status": state.status,
        "commands": commands,
        "command_count": len(commands),
        "executed_commands": state.executed_commands
    }

@app.get("/tasks")
async def list_tasks(limit: int = 10):
    """Get a list of all tasks."""
    tasks = state_manager.list_tasks(limit=limit)
    return {"tasks": tasks, "count": len(tasks)}

def process_task(task_id: str, task: str, execute: bool):
    """Process a task in the background."""
    try:
        # Update state to processing
        state = state_manager.get_state(task_id)
        state.status = "running"
        state_manager.save_state(state)
        
        # Generate execution plan
        logger.info(f"Task {task_id}: Generating execution plan")
        plan = command_generator.generate_execution_plan(task)
        
        # Update state with plan
        state_manager.update_plan(task_id, plan)
        
        if execute:
            # Execute the plan
            logger.info(f"Task {task_id}: Executing plan")
            results = execution_engine.execute_plan(plan)
            
            # Record execution results
            for step_result in results.get("steps_results", []):
                for cmd_result in step_result.get("commands_executed", []):
                    state_manager.record_command(task_id, cmd_result.get("command", ""), cmd_result)
            
            # Record adaptations
            for adaptation in results.get("adaptations", []):
                state_manager.record_adaptation(task_id, adaptation)
            
            # Analyze results with LLM if API key is available
            if llm_service.api_key:
                logger.info(f"Task {task_id}: Analyzing results with LLM")
                analysis = llm_service.analyze_verification_results(plan, results)
                state_manager.set_variable(task_id, "analysis", analysis)
            
            # Update state with status
            state_manager.complete_task(task_id, results.get("success", False))
        else:
            # Simply mark as completed with plan only
            state_manager.complete_task(task_id, True)
            
        logger.info(f"Task {task_id}: Processing completed")
    
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        state_manager.complete_task(task_id, False)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8082, reload=True)
