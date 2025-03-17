# agent-system/api/chat_routes.py

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime
import logging

# Import our custom modules
from utils.state_manager import StateManager
from utils.llm_service import LLMService
from agents.enhanced_command_generator import EnhancedCommandGenerator
from agents.execution_engine import ExecutionEngine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize components
state_manager = None
llm_service = None
command_generator = None
execution_engine = None

# Models for request/response validation
class ChatRequest(BaseModel):
    message: str
    execute: Optional[bool] = False
    task_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    task_id: Optional[str] = None
    status: Optional[str] = None
    command_outputs: Optional[List[Dict[str, Any]]] = None

def initialize_components(
    state_mgr: StateManager,
    llm_svc: LLMService,
    cmd_gen: EnhancedCommandGenerator,
    exec_engine: ExecutionEngine
):
    """Initialize the components required for chat routes."""
    global state_manager, llm_service, command_generator, execution_engine
    state_manager = state_mgr
    llm_service = llm_svc
    command_generator = cmd_gen
    execution_engine = exec_engine
    logger.info("Chat routes components initialized")

def process_task(task_id: str, message: str, execute: bool):
    """
    Process a task based on a user message.
    
    Args:
        task_id: Task identifier
        message: User message
        execute: Whether to execute commands
    """
    try:
        # Update the state
        state = state_manager.get_state(task_id)
        
        # Generate execution plan
        plan = command_generator.generate_execution_plan(message)
        
        # Update state with plan
        state_manager.update_plan(task_id, plan)
        
        if execute:
            # Execute the plan
            results = execution_engine.execute_plan(plan)
            
            # Record execution results in state
            state = state_manager.get_state(task_id)
            
            for step_result in results.get("steps_results", []):
                for cmd_result in step_result.get("commands_executed", []):
                    state_manager.record_command(task_id, cmd_result.get("command", ""), cmd_result)
            
            # Record any adaptations
            for adaptation in results.get("adaptations", []):
                state_manager.record_adaptation(task_id, adaptation)
            
            # Update state with status
            state_manager.complete_task(task_id, results.get("success", False))
        else:
            # Simply mark as completed with plan only
            state_manager.complete_task(task_id, True)
    
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        state_manager.complete_task(task_id, False)

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Handle chat messages from the user.
    
    Args:
        request: Chat request containing message, execute flag, and optional task_id
        background_tasks: FastAPI background tasks
        
    Returns:
        Chat response
    """
    # Validate dependencies
    if not all([state_manager, llm_service, command_generator, execution_engine]):
        raise HTTPException(status_code=500, detail="Chat components not properly initialized")
    
    # Handle continuing a conversation or starting a new one
    task_id = request.task_id
    
    if task_id:
        # Check if task exists
        state = state_manager.get_state(task_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")
        
        # Add message to conversation history
        state_manager.add_conversation(task_id, "user", request.message)
        
        # Generate response based on state
        response = llm_service.generate_response_to_user(state.to_dict())
        
        # Add response to conversation history
        state_manager.add_conversation(task_id, "assistant", response)
        
        return {
            "response": response,
            "task_id": task_id,
            "status": state.status
        }
    else:
        # Create a new task
        task_id = str(uuid.uuid4())
        
        # Initialize state
        state = state_manager.create_state(task_id, request.message)
        
        # Add initial messages to conversation history
        state_manager.add_conversation(task_id, "user", request.message)
        
        # Process task in background
        background_tasks.add_task(
            process_task,
            task_id=task_id,
            message=request.message,
            execute=request.execute
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

@router.get("/chat/{task_id}/status")
async def get_chat_status(task_id: str):
    """
    Get the status of a chat task.
    
    Args:
        task_id: Task identifier
        
    Returns:
        Task status details
    """
    # Check if task exists
    state = state_manager.get_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")
    
    # Return status
    return {
        "task_id": task_id,
        "status": state.status,
        "current_step": state.current_step,
        "total_steps": state.total_steps,
        "start_time": state.start_time,
        "end_time": state.end_time
    }

@router.get("/chat/{task_id}/conversation")
async def get_chat_conversation(task_id: str):
    """
    Get the conversation history for a chat task.
    
    Args:
        task_id: Task identifier
        
    Returns:
        Conversation history
    """
    # Check if task exists
    state = state_manager.get_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")
    
    # Return conversation history
    return {
        "task_id": task_id,
        "conversation": state.conversation_history
    }
