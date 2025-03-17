import uuid
import requests
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends

from config import KNOWLEDGE_SYSTEM_URL, COMMAND_EXECUTOR_URL, VM_MANAGER_URL, logger
from models.models import TaskRequest, ChatRequest, TaskStatus, ChatResponse, ResetVMRequest
from api.ui_handler import serve_frontend
from handlers.chat_handler import handle_chat_request
from handlers.vm_manager import create_vm_for_task, reset_vm, get_vm_details
from handlers.task_processor import process_task
from handlers.command_handler import execute_command_on_vm, execute_command_locally


router = APIRouter()

# Dépendances pour obtenir les composants
async def get_components():
    from main import command_generator, execution_engine, state_manager, llm_service
    return command_generator, execution_engine, state_manager, llm_service

@router.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return ui_handler.serve_frontend()

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check components' health
    vm_manager_healthy = False
    try:
        vm_response = requests.get(f"{VM_MANAGER_URL}/health", timeout=5)
        vm_manager_healthy = vm_response.status_code == 200
    except Exception:
        logger.warning("VM Manager health check failed")
    
    knowledge_system_healthy = False
    try:
        knowledge_response = requests.get(f"{KNOWLEDGE_SYSTEM_URL}/health", timeout=5)
        knowledge_system_healthy = knowledge_response.status_code == 200
    except Exception:
        logger.warning("Knowledge System health check failed")
    
    command_executor_healthy = False
    try:
        executor_response = requests.get(f"{COMMAND_EXECUTOR_URL}/health", timeout=5)
        command_executor_healthy = executor_response.status_code == 200
    except Exception:
        logger.warning("Command Executor health check failed")
    
    # Get components
    command_generator, execution_engine, state_manager, llm_service = await get_components()
    
    return {
        "status": "healthy",
        "components": {
            "api": "healthy",
            "vm_manager": "healthy" if vm_manager_healthy else "unhealthy",
            "knowledge_system": "healthy" if knowledge_system_healthy else "unhealthy",
            "command_executor": "healthy" if command_executor_healthy else "unhealthy",
            "state_manager": "healthy",
            "execution_engine": "healthy",
            "command_generator": "healthy",
            "llm_service": "healthy" if llm_service.api_key else "missing API key"
        }
    }

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
        task_processor.process_task,
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
        "details": {"estimated_completion_time": task_request.timeout}
    }

@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """Handle chat messages and process instructions."""
    # Get components
    command_generator, execution_engine, state_manager, llm_service = await get_components()
    
    # Process the chat request
    if request.task_id:
        response = await chat_handler.handle_chat_request(
            request, 
            command_generator, 
            execution_engine, 
            state_manager, 
            llm_service
        )
        return response
    else:
        # Create a new task
        task_id = str(uuid.uuid4())
        
        # Initialize state
        state = state_manager.create_state(task_id, request.message)
        
        # Add initial message to conversation history
        state_manager.add_conversation(task_id, "user", request.message)
        
        # Process task in background
        background_tasks.add_task(
            task_processor.process_task,
            task_id=task_id,
            task=request.message,
            execute=request.execute,
            command_generator=command_generator,
            execution_engine=execution_engine,
            state_manager=state_manager
        )
        
        # Generate initial response
        response = f"I'll help you with that task. I'm now processing: '{request.message}'"
        
        # Add response to conversation history
        state_manager.add_conversation(task_id, "assistant", response)
        
        return {
            "response": response,
            "task_id": task_id,
            "status": "initializing"
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
        "executed_commands": state.executed_commands,
    }
    
    # Add command outputs if available
    if state.command_outputs:
        response["command_outputs"] = state.command_outputs
    
    # Add execution plan if available
    if state.execution_plan:
        response["execution_plan"] = state.execution_plan
    
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
    if state.execution_plan and "steps" in state.execution_plan:
        for step in state.execution_plan["steps"]:
            if "commands" in step:
                commands.extend(step["commands"])
    
    return {
        "request_id": task_id,
        "task": state.task,
        "status": state.status,
        "commands": commands,
        "command_count": len(commands),
        "executed_commands": state.executed_commands
    }

@router.get("/api/tasks/{task_id}/vm")
async def get_task_vm(task_id: str):
    """Get the VM information for a specific task."""
    # Get components
    _, _, state_manager, _ = await get_components()
    
    state = state_manager.get_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get VM info from state
    vm_id = state_manager.get_variable(task_id, "vm_id")
    if not vm_id:
        raise HTTPException(status_code=404, detail="No VM found for this task")
    
    # Get VM details from VM Manager
    return await vm_manager.get_vm_details(vm_id)

@router.post("/api/tasks/{task_id}/reset-vm")
async def reset_task_vm(task_id: str, request: ResetVMRequest = ResetVMRequest()):
    """Reset the VM for a specific task."""
    # Get components
    _, _, state_manager, _ = await get_components()
    
    state = state_manager.get_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get VM info from state
    vm_id = state_manager.get_variable(task_id, "vm_id")
    if not vm_id:
        raise HTTPException(status_code=404, detail="No VM found for this task")
    
    # Reset the VM
    result = await vm_manager.reset_vm(vm_id, request.force)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to reset VM")
    
    return {
        "message": "VM reset initiated",
        "vm_id": vm_id,
        "task_id": task_id
    }

@router.get("/api/tasks")
async def list_tasks(limit: int = 10):
    """Get a list of tasks."""
    # Get components
    _, _, state_manager, _ = await get_components()
    
    tasks = state_manager.list_tasks(limit=limit)
    return {"tasks": tasks, "count": len(tasks)}
