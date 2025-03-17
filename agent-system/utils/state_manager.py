# agent-system/utils/state_manager.py

import json
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ExecutionState:
    """
    Data class representing the current state of an execution.
    """
    def __init__(self, task_id: str, task: str):
        self.task_id = task_id
        self.task = task
        self.start_time = datetime.now().isoformat()
        self.end_time = None
        self.current_step = 0
        self.total_steps = 0
        self.status = "initializing"  # initializing, running, completed, failed
        self.execution_plan = {}
        self.executed_commands = []
        self.command_outputs = {}
        self.variables = {}
        self.adaptations = []
        self.conversation_history = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for storage."""
        return {
            "task_id": self.task_id,
            "task": self.task,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "status": self.status,
            "execution_plan": self.execution_plan,
            "executed_commands": self.executed_commands,
            "command_outputs": self.command_outputs,
            "variables": self.variables,
            "adaptations": self.adaptations,
            "conversation_history": self.conversation_history
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionState':
        """Create state object from dictionary."""
        state = cls(data["task_id"], data["task"])
        state.start_time = data.get("start_time", state.start_time)
        state.end_time = data.get("end_time")
        state.current_step = data.get("current_step", 0)
        state.total_steps = data.get("total_steps", 0)
        state.status = data.get("status", "initializing")
        state.execution_plan = data.get("execution_plan", {})
        state.executed_commands = data.get("executed_commands", [])
        state.command_outputs = data.get("command_outputs", {})
        state.variables = data.get("variables", {})
        state.adaptations = data.get("adaptations", [])
        state.conversation_history = data.get("conversation_history", [])
        return state

class StateManager:
    """
    Manages execution state for tasks, providing persistence and retrieval.
    """
    
    def __init__(self, state_dir: str = None):
        """
        Initialize the state manager.
        
        Args:
            state_dir: Directory for storing state files
        """
        # Set default path if not provided
        if state_dir is None:
            data_dir = os.environ.get('DATA_DIR', '/app/data')
            state_dir = os.path.join(data_dir, 'states')
        
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)
        logger.info(f"State Manager initialized with state directory: {state_dir}")
    
    def create_state(self, task_id: str, task: str) -> ExecutionState:
        """
        Create a new execution state for a task.
        
        Args:
            task_id: Unique identifier for the task
            task: Task description
            
        Returns:
            New execution state object
        """
        state = ExecutionState(task_id, task)
        self.save_state(state)
        logger.info(f"Created new execution state for task {task_id}")
        return state
    
    def get_state(self, task_id: str) -> Optional[ExecutionState]:
        """
        Retrieve execution state for a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Execution state or None if not found
        """
        state_file = os.path.join(self.state_dir, f"{task_id}.json")
        
        if not os.path.exists(state_file):
            logger.warning(f"State file not found for task {task_id}")
            return None
        
        try:
            with open(state_file, 'r') as f:
                data = json.load(f)
            
            state = ExecutionState.from_dict(data)
            logger.info(f"Retrieved execution state for task {task_id}")
            return state
        except Exception as e:
            logger.error(f"Error retrieving state for task {task_id}: {str(e)}")
            return None
    
    def save_state(self, state: ExecutionState) -> bool:
        """
        Save execution state to persistent storage.
        
        Args:
            state: Execution state object
            
        Returns:
            True if successful, False otherwise
        """
        state_file = os.path.join(self.state_dir, f"{state.task_id}.json")
        
        try:
            with open(state_file, 'w') as f:
                json.dump(state.to_dict(), f, indent=2)
            
            logger.info(f"Saved execution state for task {state.task_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving state for task {state.task_id}: {str(e)}")
            return False
    
    def update_plan(self, task_id: str, execution_plan: Dict[str, Any]) -> bool:
        """
        Update the execution plan in the state.
        
        Args:
            task_id: Task identifier
            execution_plan: Updated execution plan
            
        Returns:
            True if successful, False otherwise
        """
        state = self.get_state(task_id)
        if not state:
            return False
        
        state.execution_plan = execution_plan
        state.total_steps = len(execution_plan.get("steps", []))
        state.status = "running"
        
        return self.save_state(state)
    
    def update_step(self, task_id: str, step: int) -> bool:
        """
        Update the current step in the state.
        
        Args:
            task_id: Task identifier
            step: Current step number
            
        Returns:
            True if successful, False otherwise
        """
        state = self.get_state(task_id)
        if not state:
            return False
        
        state.current_step = step
        
        return self.save_state(state)
    
    def record_command(self, task_id: str, command: str, output: Dict[str, Any]) -> bool:
        """
        Record a command execution in the state.
        
        Args:
            task_id: Task identifier
            command: Executed command
            output: Command execution output
            
        Returns:
            True if successful, False otherwise
        """
        state = self.get_state(task_id)
        if not state:
            return False
        
        state.executed_commands.append(command)
        state.command_outputs[command] = output
        
        return self.save_state(state)
    
    def record_adaptation(self, task_id: str, adaptation: Dict[str, Any]) -> bool:
        """
        Record an adaptation in the state.
        
        Args:
            task_id: Task identifier
            adaptation: Adaptation details
            
        Returns:
            True if successful, False otherwise
        """
        state = self.get_state(task_id)
        if not state:
            return False
        
        state.adaptations.append(adaptation)
        
        return self.save_state(state)
    
    def set_variable(self, task_id: str, key: str, value: Any) -> bool:
        """
        Set a variable in the state.
        
        Args:
            task_id: Task identifier
            key: Variable name
            value: Variable value
            
        Returns:
            True if successful, False otherwise
        """
        state = self.get_state(task_id)
        if not state:
            return False
        
        state.variables[key] = value
        
        return self.save_state(state)
    
    def get_variable(self, task_id: str, key: str, default: Any = None) -> Any:
        """
        Get a variable from the state.
        
        Args:
            task_id: Task identifier
            key: Variable name
            default: Default value if not found
            
        Returns:
            Variable value or default
        """
        state = self.get_state(task_id)
        if not state:
            return default
        
        return state.variables.get(key, default)
    
    def add_conversation(self, task_id: str, role: str, content: str) -> bool:
        """
        Add a conversation message to the state.
        
        Args:
            task_id: Task identifier
            role: Message role (user, system, assistant)
            content: Message content
            
        Returns:
            True if successful, False otherwise
        """
        state = self.get_state(task_id)
        if not state:
            return False
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        state.conversation_history.append(message)
        
        return self.save_state(state)
    
    def complete_task(self, task_id: str, success: bool) -> bool:
        """
        Mark a task as completed in the state.
        
        Args:
            task_id: Task identifier
            success: Whether the task was successful
            
        Returns:
            True if the state was updated successfully, False otherwise
        """
        state = self.get_state(task_id)
        if not state:
            return False
        
        state.status = "completed" if success else "failed"
        state.end_time = datetime.now().isoformat()
        
        return self.save_state(state)
    
    def list_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List recent tasks.
        
        Args:
            limit: Maximum number of tasks to return
            
        Returns:
            List of task summaries
        """
        tasks = []
        
        try:
            # List all state files in reverse order (newest first)
            state_files = sorted(
                [f for f in os.listdir(self.state_dir) if f.endswith('.json')],
                key=lambda x: os.path.getmtime(os.path.join(self.state_dir, x)),
                reverse=True
            )
            
            # Take only up to the limit
            state_files = state_files[:limit]
            
            # Load each state file
            for state_file in state_files:
                task_id = state_file[:-5]  # Remove .json extension
                state = self.get_state(task_id)
                if state:
                    tasks.append({
                        "task_id": state.task_id,
                        "task": state.task,
                        "status": state.status,
                        "start_time": state.start_time,
                        "end_time": state.end_time,
                        "current_step": state.current_step,
                        "total_steps": state.total_steps
                    })
        except Exception as e:
            logger.error(f"Error listing tasks: {str(e)}")
        
        return tasks
