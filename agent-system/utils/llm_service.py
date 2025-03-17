# agent-system/utils/llm_service.py

import requests
import json
import os
import logging
import time
from typing import List, Dict, Any, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LLMService:
    """
    Service for interacting with language models for intelligent task planning and analysis.
    """
    
    def __init__(self, api_key: str = None, model: str = "gpt-3.5-turbo"):
        """
        Initialize the LLM service.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY environment variable)
            model: Model to use for completions
        """
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            logger.warning("No API key provided for LLM service")
            
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"
        logger.info(f"LLM Service initialized with model: {model}")
    
    def analyze_command_output(self, command: str, output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze command output to extract insights and determine next steps.
        
        Args:
            command: The executed command
            output: Command execution output
            
        Returns:
            Analysis results
        """
        if not self.api_key:
            return {"error": "No API key configured", "analysis": "Unable to analyze without API key"}
        
        prompt = self._create_analysis_prompt(command, output)
        response = self._call_llm(prompt)
        
        # Extract the analysis
        analysis = response.get("content", "No analysis available")
        
        # Try to parse structured data from the analysis
        structured_analysis = self._extract_structured_data(analysis)
        
        return {
            "command": command,
            "success": output.get("success", False),
            "analysis": analysis,
            "structured_analysis": structured_analysis,
            "next_steps": structured_analysis.get("next_steps", []),
            "variables": structured_analysis.get("variables", {})
        }
    
    def generate_execution_plan(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate an execution plan for a task using LLM.
        
        Args:
            task: Task description
            context: Additional context for the task
            
        Returns:
            Execution plan
        """
        if not self.api_key:
            return {"error": "No API key configured", "plan": self._generate_fallback_plan(task)}
        
        prompt = self._create_planning_prompt(task, context)
        response = self._call_llm(prompt)
        
        # Extract the plan
        plan_text = response.get("content", "")
        
        # Try to parse structured data from the plan
        structured_plan = self._extract_structured_data(plan_text)
        
        # Ensure the plan has the expected structure
        if not structured_plan.get("steps"):
            structured_plan = self._generate_fallback_plan(task)
        
        return structured_plan
    
    def analyze_verification_results(self, plan: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze verification results to determine if task was successful.
        
        Args:
            plan: The execution plan
            results: Verification results
            
        Returns:
            Analysis of verification results
        """
        if not self.api_key:
            return {
                "success": results.get("success", False),
                "analysis": "Unable to perform detailed analysis without API key",
                "summary": "Task completion status is based on command exit codes only"
            }
        
        prompt = self._create_verification_prompt(plan, results)
        response = self._call_llm(prompt)
        
        # Extract the analysis
        analysis = response.get("content", "No analysis available")
        
        # Try to parse structured data from the analysis
        structured_analysis = self._extract_structured_data(analysis)
        
        return {
            "success": structured_analysis.get("success", results.get("success", False)),
            "analysis": analysis,
            "summary": structured_analysis.get("summary", "Task completed"),
            "issues": structured_analysis.get("issues", []),
            "recommendations": structured_analysis.get("recommendations", [])
        }
    
    def generate_response_to_user(self, state: Dict[str, Any]) -> str:
        """
        Generate a natural language response to the user based on task execution.
        
        Args:
            state: Current execution state
            
        Returns:
            Human-readable response
        """
        if not self.api_key:
            # Generate a simple response based on the state
            status = state.get("status", "unknown")
            task = state.get("task", "")
            
            if status == "completed":
                return f"Task '{task}' has been completed successfully."
            elif status == "failed":
                return f"Task '{task}' could not be completed. Please check the execution logs for details."
            else:
                return f"Task '{task}' is currently in status: {status}"
        
        prompt = self._create_response_prompt(state)
        response = self._call_llm(prompt)
        
        return response.get("content", "No response available")
    
    def _call_llm(self, prompt: Union[str, List[Dict[str, str]]]) -> Dict[str, Any]:
        """
        Call the language model API.
        
        Args:
            prompt: Prompt text or messages list
            
        Returns:
            Model response
        """
        # Convert string prompt to messages format if needed
        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = prompt
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.2,  # Lower temperature for more deterministic outputs
                "max_tokens": 2000
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"LLM API error: {response.status_code}, {response.text}")
                return {"content": f"Error: {response.status_code}", "error": response.text}
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            return {"content": content}
            
        except Exception as e:
            logger.error(f"Error calling LLM API: {str(e)}")
            return {"content": f"Error: {str(e)}", "error": str(e)}
    
    def _create_analysis_prompt(self, command: str, output: Dict[str, Any]) -> List[Dict[str, str]]:
        """Create a prompt for command output analysis."""
        stdout = output.get("stdout", "")
        stderr = output.get("stderr", "")
        exit_code = output.get("exit_code", -1)
        
        system_message = """
        You are a Linux system analysis assistant. Analyze command outputs to extract key information, 
        identify issues, and suggest next steps. Return your analysis in the following JSON format:
        {
            "summary": "Brief summary of what happened",
            "success": true/false,
            "key_info": ["List of key pieces of information extracted"],
            "issues": ["List of issues identified, if any"],
            "next_steps": ["Suggested next commands or actions"],
            "variables": {"key1": "value1", "key2": "value2"} // Any extracted values to store
        }
        """
        
        user_message = f"""
        Analyze the output of this Linux command:
        
        COMMAND: {command}
        EXIT CODE: {exit_code}
        
        STDOUT:
        {stdout}
        
        STDERR:
        {stderr}
        
        Please provide a detailed analysis following the JSON format specified.
        """
        
        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
    
    def _create_planning_prompt(self, task: str, context: Dict[str, Any] = None) -> List[Dict[str, str]]:
        """Create a prompt for execution planning."""
        context_text = ""
        if context:
            context_text = "Additional context:\n"
            for key, value in context.items():
                context_text += f"- {key}: {value}\n"
        
        system_message = """
        You are a Linux system administration assistant. Generate a detailed execution plan for tasks.
        Your plan should include all necessary steps, commands, and verification checks.
        Return your plan in the following JSON format:
        {
            "task": "Task description",
            "steps": [
                {
                    "name": "Step name",
                    "description": "Description of what this step does",
                    "commands": ["command1", "command2"],
                    "verification": "verification command",
                    "requires_output_analysis": true/false
                }
            ],
            "verification": "Final verification command"
        }
        
        Focus on using standard Linux commands and utilities. Ensure your plan is efficient and follows best practices.
        """
        
        user_message = f"""
        Generate an execution plan for the following task:
        
        TASK: {task}
        
        {context_text}
        
        Please provide a detailed plan following the JSON format specified.
        """
        
        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
    
    def _create_verification_prompt(self, plan: Dict[str, Any], results: Dict[str, Any]) -> List[Dict[str, str]]:
        """Create a prompt for verification analysis."""
        system_message = """
        You are a Linux system verification assistant. Analyze execution results to determine if a task was successful.
        Return your analysis in the following JSON format:
        {
            "success": true/false,
            "summary": "Summary of verification results",
            "issues": ["List of issues identified, if any"],
            "recommendations": ["Suggested actions to fix issues, if any"]
        }
        
        Focus on accurate assessment based on the evidence provided.
        """
        
        # Prepare a summary of the plan and results
        plan_summary = json.dumps(plan, indent=2)
        results_summary = json.dumps(results, indent=2)
        
        user_message = f"""
        Analyze the verification results for the following execution plan:
        
        EXECUTION PLAN:
        {plan_summary}
        
        EXECUTION RESULTS:
        {results_summary}
        
        Please provide a detailed analysis following the JSON format specified.
        """
        
        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
    
    def _create_response_prompt(self, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Create a prompt for generating a response to the user."""
        system_message = """
        You are a helpful Linux system administration assistant. Generate a natural language response for a user
        based on the execution of their requested task. Your response should be:
        1. Clear and concise
        2. Informative about what was done
        3. Highlight any issues encountered and how they were handled
        4. Provide recommendations if applicable
        
        Use a professional but friendly tone.
        """
        
        # Prepare a summary of the state
        state_summary = json.dumps(state, indent=2)
        
        user_message = f"""
        Generate a response to the user based on this task execution state:
        
        {state_summary}
        
        Your response should summarize what happened during execution and provide useful information to the user.
        """
        
        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
    
    def _extract_structured_data(self, text: str) -> Dict[str, Any]:
        """
        Extract structured JSON data from text.
        
        Args:
            text: Text potentially containing JSON
            
        Returns:
            Extracted structured data or empty dict if extraction fails
        """
        try:
            # Look for JSON pattern in the text
            json_start = text.find('{')
            json_end = text.rfind('}')
            
            if json_start >= 0 and json_end > json_start:
                json_text = text[json_start:json_end+1]
                return json.loads(json_text)
            
            return {}
        except Exception as e:
            logger.warning(f"Error extracting structured data: {str(e)}")
            return {}
    
    def _generate_fallback_plan(self, task: str) -> Dict[str, Any]:
        """
        Generate a basic fallback plan when LLM generation fails.
        
        Args:
            task: Task description
            
        Returns:
            Basic execution plan
        """
        task_lower = task.lower()
        plan = {
            "task": task,
            "steps": [],
            "verification": "echo 'Task completed'"
        }
        
        # Simple pattern matching for common tasks
        if "memory" in task_lower or "ram" in task_lower:
            plan["steps"].append({
                "name": "Check memory usage",
                "description": "Display current memory usage",
                "commands": ["free -h"],
                "verification": "echo $?",
                "requires_output_analysis": True
            })
            plan["verification"] = "free -h"
        elif "disk" in task_lower or "storage" in task_lower:
            plan["steps"].append({
                "name": "Check disk usage",
                "description": "Display current disk usage",
                "commands": ["df -h"],
                "verification": "echo $?",
                "requires_output_analysis": True
            })
            plan["verification"] = "df -h"
        elif "cpu" in task_lower or "processor" in task_lower:
            plan["steps"].append({
                "name": "Check CPU usage",
                "description": "Display current CPU usage",
                "commands": ["top -bn1 | head -20"],
                "verification": "echo $?",
                "requires_output_analysis": True
            })
            plan["verification"] = "uptime"
        elif "network" in task_lower:
            plan["steps"].append({
                "name": "Check network connections",
                "description": "Display current network connections",
                "commands": ["netstat -tuln"],
                "verification": "echo $?",
                "requires_output_analysis": True
            })
            plan["verification"] = "ping -c 4 8.8.8.8"
        elif "process" in task_lower:
            plan["steps"].append({
                "name": "Check running processes",
                "description": "Display current running processes",
                "commands": ["ps aux | head -20"],
                "verification": "echo $?",
                "requires_output_analysis": True
            })
            plan["verification"] = "uptime"
        else:
            # Very basic fallback
            plan["steps"].append({
                "name": "Execute basic command",
                "description": "List current directory",
                "commands": ["ls -la"],
                "verification": "echo $?",
                "requires_output_analysis": False
            })
        
        return plan
