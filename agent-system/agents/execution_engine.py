# agent-system/agents/execution_engine.py

import logging
import subprocess
import time
import re
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ExecutionEngine:
    """
    Advanced execution engine that handles command execution with feedback analysis.
    """
    
    def __init__(self, dry_run=True, timeout=60):
        """
        Initialize the execution engine.
        
        Args:
            dry_run: Whether to simulate execution without running commands
            timeout: Default command timeout in seconds
        """
        self.dry_run = dry_run
        self.timeout = timeout
        logger.info(f"Execution Engine initialized (dry_run={dry_run}, timeout={timeout})")
    
    def execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a complete plan with adaptive feedback loops.
        
        Args:
            plan: The execution plan with steps and commands
            
        Returns:
            Execution results with outputs and adaptations
        """
        if self.dry_run:
            logger.info("DRY RUN MODE: Commands will be simulated")
            
        # Initialize result structure
        result = {
            "task": plan.get("task", "Unknown task"),
            "steps_executed": 0,
            "steps_total": len(plan.get("steps", [])),
            "success": False,
            "steps_results": [],
            "verification_result": None,
            "adaptations": []
        }
        
        # Execute each step in the plan
        steps = plan.get("steps", [])
        step_count = 0
        
        for step in steps:
            step_count += 1
            step_name = step.get("name", f"Step {step_count}")
            commands = step.get("commands", [])
            verification_cmd = step.get("verification")
            requires_analysis = step.get("requires_output_analysis", False)
            
            logger.info(f"Executing step: {step_name} ({step_count}/{len(steps)})")
            
            # Initialize step result
            step_result = {
                "name": step_name,
                "commands_executed": [],
                "success": True
            }
            
            # Execute commands in the step
            for cmd in commands:
                # Execute the command
                cmd_result = self._execute_command(cmd)
                step_result["commands_executed"].append(cmd_result)
                
                # If command failed and needs analysis, try to adapt
                if not cmd_result["success"] and requires_analysis:
                    adaptation = self._analyze_and_adapt(cmd, cmd_result)
                    if adaptation:
                        result["adaptations"].append(adaptation)
                        # Execute the adapted command
                        adapted_cmd = adaptation.get("adapted_command")
                        if adapted_cmd:
                            logger.info(f"Executing adapted command: {adapted_cmd}")
                            adapted_result = self._execute_command(adapted_cmd)
                            step_result["commands_executed"].append(adapted_result)
                            # Update success flag based on adaptation result
                            if adapted_result["success"]:
                                cmd_result["success"] = True
                
                # If command failed (even after adaptation), mark step as failed
                if not cmd_result["success"]:
                    step_result["success"] = False
                    logger.warning(f"Command failed: {cmd}")
                    # Don't proceed with remaining commands in this step if a command fails
                    break
            
            # Execute verification command if provided
            if verification_cmd and step_result["success"]:
                logger.info(f"Executing verification: {verification_cmd}")
                verification_result = self._execute_command(verification_cmd)
                step_result["verification"] = verification_result
                
                # If verification fails, mark step as failed
                if not verification_result["success"]:
                    step_result["success"] = False
                    logger.warning(f"Verification failed for step: {step_name}")
            
            # Add step result to the overall result
            result["steps_results"].append(step_result)
            
            # Don't proceed with remaining steps if a step fails
            if not step_result["success"]:
                logger.warning(f"Step failed: {step_name}")
                break
            
            # Update steps executed count
            result["steps_executed"] += 1
        
        # Execute overall plan verification if provided
        verification_cmd = plan.get("verification")
        if verification_cmd:
            logger.info(f"Executing plan verification: {verification_cmd}")
            verification_result = self._execute_command(verification_cmd)
            result["verification_result"] = verification_result
            
            # Update overall success based on verification
            result["success"] = (result["steps_executed"] == result["steps_total"] and 
                                verification_result.get("success", False))
        else:
            # Without verification, success depends only on steps completion
            result["success"] = result["steps_executed"] == result["steps_total"]
        
        logger.info(f"Plan execution completed: {result['steps_executed']}/{result['steps_total']} steps, " +
                    f"success={result['success']}")
        
        return result
    
    def _execute_command(self, command: str) -> Dict[str, Any]:
        """
        Execute a single command and capture the results.
        
        Args:
            command: The command to execute
            
        Returns:
            Execution result
        """
        result = {
            "command": command,
            "success": False,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "execution_time": 0.0
        }
        
        # Skip execution in dry run mode
        if self.dry_run:
            result["stdout"] = f"[DRY RUN] Command would be executed: {command}"
            result["success"] = True
            result["exit_code"] = 0
            return result
        
        # Execute the command
        try:
            start_time = time.time()
            
            # Execute command with timeout
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            # Capture execution time
            execution_time = time.time() - start_time
            
            # Populate result with process output
            result["stdout"] = process.stdout
            result["stderr"] = process.stderr
            result["exit_code"] = process.returncode
            result["success"] = process.returncode == 0
            result["execution_time"] = execution_time
            
            logger.info(f"Command executed: {command} (exit_code={process.returncode}, time={execution_time:.2f}s)")
            
        except subprocess.TimeoutExpired:
            result["stderr"] = f"Command timed out after {self.timeout} seconds"
            result["exit_code"] = 124  # Consistent with timeout command
            logger.error(f"Command timed out: {command}")
            
        except Exception as e:
            result["stderr"] = f"Error executing command: {str(e)}"
            logger.error(f"Error executing command: {command}, error: {str(e)}")
        
        return result
    
    def _analyze_and_adapt(self, cmd: str, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze command failure and generate adaptive solutions.
        
        Args:
            cmd: The failed command
            result: The execution result
            
        Returns:
            Adaptation strategy or None if no adaptation is possible
        """
        stderr = result.get("stderr", "")
        stdout = result.get("stdout", "")
        
        # Initialize adaptation
        adaptation = {
            "original_command": cmd,
            "error": stderr,
            "adaptation_reason": None,
            "adapted_command": None
        }
        
        # Pattern match common errors and adapt
        if "command not found" in stderr:
            # Missing command/package
            command_name = cmd.split()[0]
            if command_name == "sudo":
                command_name = cmd.split()[1] if len(cmd.split()) > 1 else "unknown"
                
            # Map common commands to packages
            cmd_to_pkg = {
                "nginx": "nginx",
                "apache2": "apache2",
                "mysql": "mysql-server",
                "mariadb": "mariadb-server",
                "postgresql": "postgresql",
                "php": "php",
                "python3": "python3",
                "node": "nodejs",
                "docker": "docker.io"
            }
            
            if command_name in cmd_to_pkg:
                package = cmd_to_pkg[command_name]
                adaptation["adaptation_reason"] = f"Command '{command_name}' not found. Installing required package."
                adaptation["adapted_command"] = f"sudo apt-get update && sudo apt-get install -y {package}"
                return adaptation
                
        elif "Permission denied" in stderr or "permission denied" in stderr:
            # Permission issues - try adding sudo
            if not cmd.startswith("sudo "):
                adaptation["adaptation_reason"] = "Permission denied. Retrying with sudo."
                adaptation["adapted_command"] = f"sudo {cmd}"
                return adaptation
                
        elif "Could not resolve host" in stderr or "Network is unreachable" in stderr:
            # Network connectivity issues
            adaptation["adaptation_reason"] = "Network connectivity issue detected"
            adaptation["adapted_command"] = "ping -c 4 8.8.8.8"
            return adaptation
                
        elif "No such file or directory" in stderr:
            # Missing file or directory
            match = re.search(r"No such file or directory: '?([^']+)'?", stderr)
            if match:
                path = match.group(1)
                # Check if this is a directory
                if '/' in path and not '.' in path.split('/')[-1]:
                    adaptation["adaptation_reason"] = f"Directory '{path}' does not exist. Creating it."
                    adaptation["adapted_command"] = f"mkdir -p {path}"
                    return adaptation
        
        # No adaptation found
        return None
