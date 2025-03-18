import uuid
import requests
import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from config import KNOWLEDGE_SYSTEM_URL, COMMAND_EXECUTOR_URL, VM_MANAGER_URL, logger
from models.models import TaskRequest, ChatRequest, TaskStatus, ChatResponse, ResetVMRequest
from api.ui_handler import serve_frontend as ui_frontend
from robust_vm_manager import RobustVMManager as VMManager

router = APIRouter()
vm_manager = VMManager()

# Dépendances pour obtenir les composants
async def get_components():
    from main import command_generator, execution_engine, state_manager, llm_service
    return command_generator, execution_engine, state_manager, llm_service

@router.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return ui_frontend()

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    # Get components
    command_generator, execution_engine, state_manager, llm_service = await get_components()
    
    # Check knowledge system health
    knowledge_system_healthy = False
    try:
        knowledge_response = requests.get(f"{KNOWLEDGE_SYSTEM_URL}/health", timeout=2)
        knowledge_system_healthy = knowledge_response.status_code == 200
    except Exception:
        logger.warning("Knowledge System health check failed")
    
    # Check VM manager availability
    vm_manager_healthy = vm_manager.is_available()
    
    return {
        "status": "healthy",
        "components": {
            "api": "healthy",
            "vm_manager": "healthy" if vm_manager_healthy else "unhealthy",
            "knowledge_system": "healthy" if knowledge_system_healthy else "unhealthy",
            "state_manager": "healthy",
            "execution_engine": "healthy",
            "command_generator": "healthy",
            "llm_service": "healthy" if llm_service.api_key else "missing API key"
        }
    }

async def process_task(task_id, task, execute, command_generator, execution_engine, state_manager):
    """Process a task and execute commands if requested."""
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
            # Execute the plan directly with execution_engine
            logger.info(f"Task {task_id}: Executing plan")
            result = execution_engine.execute_plan(plan)
            success = result.get("success", False)
            
            # Record execution results
            for step_result in result.get("steps_results", []):
                for cmd_result in step_result.get("commands_executed", []):
                    state_manager.record_command(task_id, cmd_result.get("command", ""), cmd_result)
        else:
            # Just mark as completed without execution
            success = True
        
        # Mark as completed
        state_manager.complete_task(task_id, success)
            
        logger.info(f"Task {task_id}: Processing completed")
            
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        state_manager.complete_task(task_id, False)

@router.post("/api/tasks", response_model=TaskStatus)
async def create_task(task_request: TaskRequest, background_tasks: BackgroundTasks):
    """Create a new task and start processing it."""
    # Generate a unique request ID
    request_id = str(uuid.uuid4())
    
    # Log the task
    logger.info(f"Received task: {task_request.task}")
    
    # Get components
    command_generator, execution_engine, state_manager, llm_service = await get_components()
    
    # Create execution state
    state = state_manager.create_state(request_id, task_request.task)
    
    # Create VM if execution is requested
    if task_request.execute:
        vm_data = await vm_manager.create_vm_for_task(request_id)
        if vm_data:
            # Store VM info in state
            state_manager.set_variable(request_id, "vm_id", vm_data["id"])
            state_manager.set_variable(request_id, "vm_info", vm_data)
    
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
    
    # Return status
    return {
        "request_id": request_id,
        "status": "accepted",
        "message": "Task has been accepted and is being processed",
        "details": {"estimated_completion_time": task_request.timeout or 300}
    }

@router.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a specific task."""
    # Get components
    _, _, state_manager, _ = await get_components()
    
    state = state_manager.get_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Convert state to response format
    response = {
        "request_id": task_id,
        "task": state.task,
        "status": state.status,
        "current_step": state.current_step,
        "total_steps": state.total_steps,
        "start_time": state.start_time,
        "end_time": state.end_time,
        "executed_commands": state.executed_commands if hasattr(state, 'executed_commands') else [],
    }
    
    # Add command outputs if available
    if hasattr(state, 'command_outputs') and state.command_outputs:
        response["command_outputs"] = state.command_outputs
    
    # Add execution plan if available
    if hasattr(state, 'execution_plan') and state.execution_plan:
        response["execution_plan"] = state.execution_plan
    
    # Add VM info if available
    vm_id = state_manager.get_variable(task_id, "vm_id")
    if vm_id:
        response["vm_id"] = vm_id
    
    return response

@router.get("/api/tasks/{task_id}/commands")
async def get_task_commands(task_id: str):
    """Get the commands for a specific task."""
    # Get components
    _, _, state_manager, _ = await get_components()
    
    state = state_manager.get_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Extract commands from execution plan
    commands = []
    if hasattr(state, 'execution_plan') and state.execution_plan and "steps" in state.execution_plan:
        for step in state.execution_plan["steps"]:
            if "commands" in step:
                commands.extend(step["commands"])
    
    return {
        "request_id": task_id,
        "task": state.task,
        "status": state.status,
        "commands": commands,
        "command_count": len(commands),
        "executed_commands": state.executed_commands if hasattr(state, 'executed_commands') else []
    }

@router.delete("/api/vms/{vm_id}")
async def destroy_vm(vm_id: str):
    """Destroy a VM completely."""
    try:
        # Get components
        _, _, state_manager, _ = await get_components()
        
        result = await vm_manager.destroy_vm(vm_id)
        if not result:
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to destroy VM", "vm_id": vm_id}
            )
        
        # Si la VM est associée à une tâche, mettre à jour l'état
        for task in state_manager.list_tasks():
            task_id = task.get("task_id")
            if task_id:
                vm_task_id = state_manager.get_variable(task_id, "vm_id")
                if vm_task_id == vm_id:
                    # Supprimer la référence à la VM dans l'état de la tâche
                    state_manager.set_variable(task_id, "vm_id", None)
                    state_manager.set_variable(task_id, "vm_destroyed", True)
                    logger.info(f"Updated task {task_id} to reflect VM destruction")
        
        return {
            "message": "VM destruction initiated",
            "vm_id": vm_id,
            "status": result.get("status", "unknown")
        }
    except Exception as e:
        logger.error(f"Error destroying VM: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to destroy VM",
                "message": str(e)
            }
        )

@router.get("/api/tasks")
async def list_tasks(limit: int = 10):
    """Get a list of tasks."""
    # Get components
    _, _, state_manager, _ = await get_components()
    
    tasks = state_manager.list_tasks(limit=limit)
    return {"tasks": tasks, "count": len(tasks)}
