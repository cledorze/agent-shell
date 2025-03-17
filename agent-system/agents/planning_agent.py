import logging
import json
import os
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import openai

logger = logging.getLogger(__name__)

class SubTask(BaseModel):
    """Represents a subtask decomposed by the planning agent."""
    id: str
    description: str
    dependencies: List[str] = []
    estimated_complexity: str
    validation_criteria: List[str] = []
    
class TaskPlan(BaseModel):
    """Represents a complete task plan."""
    request_id: str
    original_task: str
    subtasks: List[SubTask]
    estimated_execution_time: int  # in seconds
    potential_issues: List[str] = []
    requires_prerequisites: bool = False
    prerequisites: List[str] = []

class PlanningAgent:
    """
    Agent responsible for decomposing complex tasks into subtasks
    that can be processed by other agents.
    """
    
    def __init__(self, model_name: str = "gpt-4", api_key: Optional[str] = None):
        """
        Initialize the planning agent.
        
        Args:
            model_name: Name of the LLM model to use
            api_key: API key for model access (optional if defined in environment)
        """
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("API key for OpenAI is required")
            
        logger.info(f"PlanningAgent initialized with model {model_name}")
        
    def create_plan(self, request_id: str, task_description: str) -> TaskPlan:
        """
        Creates a detailed execution plan from a task description.
        
        Args:
            request_id: Unique request identifier
            task_description: Task description in natural language
            
        Returns:
            TaskPlan: A structured plan with subtasks and dependencies
        """
        logger.info(f"Creating plan for task: {task_description}")
        
        # Build prompt for LLM
        prompt = self._build_planning_prompt(task_description)
        
        try:
            # Call LLM to generate plan
            response = openai.ChatCompletion.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a Linux system administration expert. Your task is to break down complex Linux administration tasks into clear, logical steps with proper dependencies."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2000,
                api_key=self.api_key
            )
            
            plan_json = response.choices[0].message.content
            # Extract JSON if needed
            if "```json" in plan_json:
                plan_json = plan_json.split("```json")[1].split("```")[0].strip()
            
            # Parse JSON to Python dict
            plan_dict = json.loads(plan_json)
            
            # Convert to Pydantic model
            subtasks = [SubTask(**subtask) for subtask in plan_dict.get("subtasks", [])]
            
            task_plan = TaskPlan(
                request_id=request_id,
                original_task=task_description,
                subtasks=subtasks,
                estimated_execution_time=plan_dict.get("estimated_execution_time", 300),
                potential_issues=plan_dict.get("potential_issues", []),
                requires_prerequisites=plan_dict.get("requires_prerequisites", False),
                prerequisites=plan_dict.get("prerequisites", [])
            )
            
            logger.info(f"Plan created with {len(subtasks)} subtasks")
            return task_plan
            
        except Exception as e:
            logger.error(f"Error creating plan: {str(e)}")
            raise
    
    def _build_planning_prompt(self, task_description: str) -> str:
        """
        Builds the prompt for the LLM to generate a plan.
        
        Args:
            task_description: Task description
            
        Returns:
            str: Formatted prompt
        """
        return f"""
        I need to create a plan to execute the following OpenSUSE Tumbleweed administration task:
        
        TASK: {task_description}
        
        Break this down into logical subtasks with dependencies. For each subtask, provide:
        1. A unique ID
        2. A clear description of what needs to be done
        3. Dependencies (IDs of subtasks that must be completed first)
        4. Estimated complexity (simple, medium, complex)
        5. Validation criteria to confirm completion
        
        Also include:
        - Estimated total execution time (in seconds)
        - Potential issues that might arise
        - Whether any prerequisites are needed
        - List of prerequisites if applicable
        
        Format your response as a JSON object with this structure:
        ```json
        {{
            "subtasks": [
                {{
                    "id": "string",
                    "description": "string",
                    "dependencies": ["string"],
                    "estimated_complexity": "string",
                    "validation_criteria": ["string"]
                }}
            ],
            "estimated_execution_time": number,
            "potential_issues": ["string"],
            "requires_prerequisites": boolean,
            "prerequisites": ["string"]
        }}
        ```
        
        Consider best practices for OpenSUSE Tumbleweed administration.
        """
    
    def refine_plan(self, plan: TaskPlan, feedback: Dict[str, Any]) -> TaskPlan:
        """
        Refines an existing plan based on feedback from other agents.
        
        Args:
            plan: Initial plan
            feedback: Feedback on detected issues
            
        Returns:
            TaskPlan: Updated plan
        """
        logger.info(f"Refining plan based on feedback")
        
        # Logic for improving the plan based on feedback
        # To be implemented as needed
        
        return plan
