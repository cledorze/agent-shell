import logging
import subprocess
import time
import os
import shlex

# Import our custom logger
from utils.logger import get_logger

class CommandExecutor:
    """
    Executes shell commands with enhanced verbosity and color output.
    """
    
    def __init__(self, direct_execution=False, dry_run=True, verbose_level=2):
        """
        Initialize the CommandExecutor.
        
        Args:
            direct_execution (bool): Whether to execute commands directly in the system shell
            dry_run (bool): Whether to only log commands without executing them
            verbose_level (int): Level of verbosity for command output (1-3)
        """
        # Configure from environment variables if present
        env_direct = os.environ.get('DIRECT_EXECUTION', 'false').lower()
        direct_execution = env_direct in ('true', 'yes', '1', 'on')
        
        env_dry_run = os.environ.get('DRY_RUN', 'true').lower()
        dry_run = env_dry_run in ('true', 'yes', '1', 'on')
        
        env_verbose = os.environ.get('VERBOSE_LEVEL')
        if env_verbose:
            try:
                verbose_level = int(env_verbose)
            except ValueError:
                pass
                
        self.direct_execution = direct_execution
        self.dry_run = dry_run
        self.verbose_level = min(max(1, verbose_level), 3)  # Clamp between 1 and 3
        
        # Initialize logger
        self.logger = get_logger("agents.command_executor", verbose_level=self.verbose_level)
        
        self.logger.info(f"CommandExecutor initialized (dry_run={dry_run}, direct_execution={direct_execution}, verbose_level={verbose_level})")
    
    def execute_command(self, command, task_id=None, shell=True, timeout=60):
        """
        Execute a shell command with proper logging and output capture.
        
        Args:
            command (str): Command to execute
            task_id (str, optional): Associated task ID for tracking
            shell (bool): Whether to use shell for execution
            timeout (int): Command timeout in seconds
            
        Returns:
            dict: Result dictionary containing:
                - command: Original command
                - success: Whether execution succeeded
                - stdout: Command standard output
                - stderr: Command standard error
                - exit_code: Command exit code
                - execution_time: Execution time in seconds
        """
        self.logger.command_start(command, task_id)
        
        result = {
            'command': command,
            'success': False,
            'stdout': '',
            'stderr': '',
            'exit_code': -1,
            'execution_time': 0.0
        }
        
        # For dry run mode, just return without execution
        if self.dry_run:
            result['stdout'] = '[DRY RUN] Command would be executed here'
            result['success'] = True
            result['exit_code'] = 0
            
            self.logger.command_result(
                command, 
                result['success'], 
                result['stdout'], 
                result['stderr'],
                result['exit_code'], 
                result['execution_time']
            )
            return result
        
        # For direct execution mode, execute the command
        if self.direct_execution:
            try:
                start_time = time.time()
                
                # Execute the command
                process = subprocess.Popen(
                    command,
                    shell=shell,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Capture output with timeout
                stdout, stderr = process.communicate(timeout=timeout)
                exit_code = process.returncode
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Update result
                result['stdout'] = stdout
                result['stderr'] = stderr
                result['exit_code'] = exit_code
                result['success'] = exit_code == 0
                result['execution_time'] = execution_time
                
            except subprocess.TimeoutExpired:
                self.logger.error(f"Command timed out after {timeout} seconds: {command}")
                result['stderr'] = f"Command timed out after {timeout} seconds"
                # Try to terminate the process
                process.kill()
                
            except Exception as e:
                self.logger.error(f"Error executing command: {str(e)}")
                result['stderr'] = f"Error executing command: {str(e)}"
        else:
            # Simulation mode
            result['stdout'] = f"[SIMULATION] Command '{command}' would be executed"
            result['success'] = True
            result['exit_code'] = 0
            result['execution_time'] = 0.01
        
        # Log the result with all details
        self.logger.command_result(
            command, 
            result['success'], 
            result['stdout'], 
            result['stderr'],
            result['exit_code'], 
            result['execution_time']
        )
        
        return result
    
    def execute_commands(self, commands, task_id=None, stop_on_error=True):
        """
        Execute multiple commands in sequence with detailed logging.
        
        Args:
            commands (list): List of commands to execute
            task_id (str, optional): Associated task ID for tracking
            stop_on_error (bool): Whether to stop execution on first error
            
        Returns:
            list: List of result dictionaries for each command
        """
        results = []
        
        if not commands:
            self.logger.warning("No commands provided for execution")
            return results
        
        self.logger.info(f"Executing {len(commands)} commands" + (f" for task {task_id}" if task_id else ""))
        
        for i, command in enumerate(commands):
            # Skip empty commands and comments
            if not command or command.strip().startswith('#'):
                if command and command.strip().startswith('#') and self.verbose_level >= 2:
                    # If it's a comment and we're in verbose mode, log it
                    self.logger.info(f"Command {i+1}/{len(commands)}: {command}")
                continue
                
            # Execute the command
            result = self.execute_command(command, task_id)
            results.append(result)
            
            # Stop on error if required
            if stop_on_error and not result['success']:
                self.logger.error(f"Stopping execution after command {i+1}/{len(commands)} failed")
                break
        
        # Summarize the execution
        success_count = sum(1 for r in results if r['success'])
        self.logger.info(f"Executed {len(results)} commands: {success_count} succeeded, {len(results) - success_count} failed")
        
        return results

# Example usage
if __name__ == "__main__":
    # Example of how to use the CommandExecutor
    executor = CommandExecutor(direct_execution=True, dry_run=False, verbose_level=3)
    
    # Test single command execution
    result = executor.execute_command("ls -la")
    print(f"Command succeeded: {result['success']}")
    
    # Test multiple commands
    commands = [
        "# This is a comment that will be displayed but not executed",
        "echo 'Hello, world!'",
        "ls -la /tmp",
        "cat /etc/os-release"
    ]
    
    results = executor.execute_commands(commands, task_id="test-task-456")
    
    # Summarize results
    for i, result in enumerate(results):
        print(f"Command {i+1}: {'Success' if result['success'] else 'Failed'}")
