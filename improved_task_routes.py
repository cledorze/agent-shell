from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
import logging
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Models for request/response
class TaskRequest(BaseModel):
    task: str
    execute: Optional[bool] = False
    priority: Optional[str] = "normal"
    timeout: Optional[int] = 300

class TaskStatus(BaseModel):
    request_id: str
    status: str
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

# Exception handler for API routes
@router.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        # Log the exception
        logger.error(f"Exception in API request: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return as JSON response
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": str(e),
                "path": request.url.path
            }
        )

# Create a minimal task processor
async def process_task(task_id, task, execute, command_generator, execution_engine, state_manager):
    try:
        # Update state to processing
        state = state_manager.get_state(task_id)
        state.status = "running"
        state_manager.save_state(state)
        
        # Generate commands
        plan = command_generator.generate_execution_plan(task)
        
        # Update state with plan
        state_manager.update_plan(task_id, plan)
        
        if execute:
            # Execute the plan
            result = execution_engine.execute_plan(plan)
            success = result.get("success", False)
        else:
            # Just mark as completed without execution
            success = True
        
        # Mark as completed
        state_manager.complete_task(task_id, success)
        
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        logger.error(traceback.format_exc())
        state_manager.complete_task(task_id, False)

@router.post("/api/tasks", response_model=TaskStatus)
async def create_task(task_request: TaskRequest, background_tasks: BackgroundTasks):
    """Create a new task and process it in the background."""
    try:
        # Get necessary components
        from main import command_generator, execution_engine, state_manager, llm_service
        
        # Generate a request ID
        request_id = str(uuid.uuid4())
        logger.info(f"Creating task {request_id}: {task_request.task}")
        
        # Create execution state
        state = state_manager.create_state(request_id, task_request.task)
        
        # Start processing in the background
        background_tasks.add_task(
            process_task,
            task_id=request_id,
            task=task_request.task,
            execute=task_request.execute,
            command_generator=command_generator,
            execution_engine=execution_engine,
            state_manager=state_manager
        )
        
        # Return the initial status
        return {
            "request_id": request_id,
            "status": "accepted",
            "message": "Task has been accepted and is being processed",
            "details": {"estimated_completion_time": task_request.timeout}
        }
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to create task",
                "message": str(e)
            }
        )

@router.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a specific task."""
    try:
        from main import state_manager
        
        state = state_manager.get_state(task_id)
        if not state:
            return JSONResponse(
                status_code=404,
                content={"error": "Task not found", "task_id": task_id}
            )
        
        response = {
            "request_id": task_id,
            "task": state.task,
            "status": state.status,
            "current_step": state.current_step,
            "total_steps": state.total_steps,
            "start_time": state.start_time,
            "end_time": state.end_time,
            "executed_commands": state.executed_commands,
        }
        
        # Add command outputs if available
        if hasattr(state, 'command_outputs') and state.command_outputs:
            response["command_outputs"] = state.command_outputs
        
        return response
    except Exception as e:
        logger.error(f"Error getting task status: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to get task status",
                "message": str(e),
                "task_id": task_id
            }
        )

@router.get("/api/tasks/{task_id}/commands")
async def get_task_commands(task_id: str):
    """Get the commands for a specific task."""
    try:
        from main import state_manager
        
        state = state_manager.get_state(task_id)
        if not state:
            return JSONResponse(
                status_code=404,
                content={"error": "Task not found", "task_id": task_id}
            )
        
        # Extract commands from execution plan
        commands = []
        if state.execution_plan and "steps" in state.execution_plan:
            for step in state.execution_plan["steps"]:
                if "commands" in step:
                    commands.extend(step["commands"])
        
        return {
            "request_id": task_id,
            "task": state.task,
            "status": state.status,
            "commands": commands,
            "command_count": len(commands)
        }
    except Exception as e:
        logger.error(f"Error getting task commands: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to get task commands",
                "message": str(e),
                "task_id": task_id
            }
        )
