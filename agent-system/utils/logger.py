import logging
import os
import sys
from datetime import datetime

# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"
    
    # Bright foreground colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds color to log messages based on their level.
    """
    FORMATS = {
        logging.DEBUG: Colors.CYAN + "%(asctime)s [%(name)s] [DEBUG] %(message)s" + Colors.RESET,
        logging.INFO: Colors.GREEN + "%(asctime)s [%(name)s] [INFO] %(message)s" + Colors.RESET,
        logging.WARNING: Colors.YELLOW + "%(asctime)s [%(name)s] [WARNING] %(message)s" + Colors.RESET,
        logging.ERROR: Colors.RED + "%(asctime)s [%(name)s] [ERROR] %(message)s" + Colors.RESET,
        logging.CRITICAL: Colors.BG_RED + Colors.WHITE + "%(asctime)s [%(name)s] [CRITICAL] %(message)s" + Colors.RESET
    }
    
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

class VerboseLogger:
    """
    Enhanced logger that provides colored and structured output with varying levels of verbosity.
    """
    def __init__(self, name, level=logging.INFO, enable_color=True, verbose_level=1):
        """
        Initialize the verbose logger.
        
        Args:
            name (str): Logger name
            level (int): Logging level (default: INFO)
            enable_color (bool): Whether to enable colored output (default: True)
            verbose_level (int): Verbosity level (1-3, with 3 being most verbose)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.enable_color = enable_color
        self.verbose_level = min(max(1, verbose_level), 3)  # Clamp between 1 and 3
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        
        # Set formatter based on color preference
        if enable_color:
            console_handler.setFormatter(ColoredFormatter())
        else:
            console_handler.setFormatter(
                logging.Formatter('%(asctime)s [%(name)s] [%(levelname)s] %(message)s', 
                                 datefmt="%Y-%m-%d %H:%M:%S")
            )
        
        self.logger.addHandler(console_handler)
    
    def debug(self, message, *args, **kwargs):
        """Log a debug message."""
        self.logger.debug(message, *args, **kwargs)
    
    def info(self, message, *args, **kwargs):
        """Log an info message."""
        self.logger.info(message, *args, **kwargs)
    
    def warning(self, message, *args, **kwargs):
        """Log a warning message."""
        self.logger.warning(message, *args, **kwargs)
    
    def error(self, message, *args, **kwargs):
        """Log an error message."""
        self.logger.error(message, *args, **kwargs)
    
    def critical(self, message, *args, **kwargs):
        """Log a critical message."""
        self.logger.critical(message, *args, **kwargs)
    
    def command_start(self, command, task_id=None):
        """
        Log the start of a command execution with appropriate formatting.
        
        Args:
            command (str): The command being executed
            task_id (str, optional): Associated task ID
        """
        task_info = f" for task {task_id}" if task_id else ""
        
        if self.enable_color:
            self.logger.info(f"Executing command{task_info}: {Colors.BRIGHT_YELLOW}{command}{Colors.RESET}")
        else:
            self.logger.info(f"Executing command{task_info}: {command}")
    
    def command_result(self, command, success, stdout=None, stderr=None, exit_code=None, execution_time=None):
        """
        Log the result of a command execution with color-coded output.
        
        Args:
            command (str): The command that was executed
            success (bool): Whether the command succeeded
            stdout (str, optional): Command stdout
            stderr (str, optional): Command stderr
            exit_code (int, optional): Command exit code
            execution_time (float, optional): Command execution time in seconds
        """
        # Format execution time if provided
        time_info = f" in {execution_time:.2f}s" if execution_time is not None else ""
        
        # Base result message
        if self.enable_color:
            status = f"{Colors.BRIGHT_GREEN}SUCCESS{Colors.RESET}" if success else f"{Colors.BRIGHT_RED}FAILED{Colors.RESET}"
            result_msg = f"Command {status}{time_info}: {Colors.BRIGHT_YELLOW}{command}{Colors.RESET}"
        else:
            status = "SUCCESS" if success else "FAILED"
            result_msg = f"Command {status}{time_info}: {command}"
        
        self.logger.info(result_msg)
        
        # Add exit code if available and verbose enough
        if exit_code is not None and self.verbose_level >= 2:
            if self.enable_color:
                code_color = Colors.GREEN if exit_code == 0 else Colors.RED
                self.logger.debug(f"Exit code: {code_color}{exit_code}{Colors.RESET}")
            else:
                self.logger.debug(f"Exit code: {exit_code}")
        
        # Add stdout if available and verbose enough
        if stdout and self.verbose_level >= 2:
            truncated = False
            output = stdout
            
            # Truncate output for lower verbosity levels
            if self.verbose_level == 2 and len(stdout) > 500:
                output = stdout[:500]
                truncated = True
            
            if self.enable_color:
                self.logger.debug(f"{Colors.BRIGHT_BLACK}--- STDOUT ---{Colors.RESET}")
                self.logger.debug(f"{Colors.WHITE}{output}{Colors.RESET}")
                if truncated:
                    self.logger.debug(f"{Colors.BRIGHT_BLACK}--- Output truncated, use higher verbosity to see full output ---{Colors.RESET}")
            else:
                self.logger.debug("--- STDOUT ---")
                self.logger.debug(output)
                if truncated:
                    self.logger.debug("--- Output truncated, use higher verbosity to see full output ---")
        
        # Add stderr if available and verbose enough
        if stderr and self.verbose_level >= 2:
            truncated = False
            error_output = stderr
            
            # Truncate output for lower verbosity levels
            if self.verbose_level == 2 and len(stderr) > 500:
                error_output = stderr[:500]
                truncated = True
            
            if self.enable_color:
                self.logger.debug(f"{Colors.BRIGHT_BLACK}--- STDERR ---{Colors.RESET}")
                self.logger.debug(f"{Colors.RED}{error_output}{Colors.RESET}")
                if truncated:
                    self.logger.debug(f"{Colors.BRIGHT_BLACK}--- Error output truncated, use higher verbosity to see full output ---{Colors.RESET}")
            else:
                self.logger.debug("--- STDERR ---")
                self.logger.debug(error_output)
                if truncated:
                    self.logger.debug("--- Error output truncated, use higher verbosity to see full output ---")
    
    def task_start(self, task_id, task_description):
        """
        Log the start of a task with distinctive formatting.
        
        Args:
            task_id (str): Task identifier
            task_description (str): Description of the task
        """
        if self.enable_color:
            self.logger.info(f"{Colors.BG_BLUE}{Colors.WHITE} TASK START {Colors.RESET} {Colors.BOLD}ID: {task_id}{Colors.RESET}")
            self.logger.info(f"{Colors.BRIGHT_CYAN}Description:{Colors.RESET} {task_description}")
        else:
            self.logger.info(f"=== TASK START === ID: {task_id}")
            self.logger.info(f"Description: {task_description}")
    
    def task_complete(self, task_id, success, message=None):
        """
        Log the completion of a task with distinctive formatting.
        
        Args:
            task_id (str): Task identifier
            success (bool): Whether the task completed successfully
            message (str, optional): Additional completion message
        """
        if self.enable_color:
            bg_color = Colors.BG_GREEN if success else Colors.BG_RED
            status = "SUCCESS" if success else "FAILED"
            self.logger.info(f"{bg_color}{Colors.WHITE} TASK {status} {Colors.RESET} {Colors.BOLD}ID: {task_id}{Colors.RESET}")
            if message:
                self.logger.info(f"{Colors.BRIGHT_CYAN}Result:{Colors.RESET} {message}")
        else:
            status = "SUCCESS" if success else "FAILED"
            self.logger.info(f"=== TASK {status} === ID: {task_id}")
            if message:
                self.logger.info(f"Result: {message}")
    
    def section(self, title):
        """
        Create a visual section divider with a title.
        
        Args:
            title (str): Section title
        """
        if self.enable_color:
            self.logger.info(f"\n{Colors.BRIGHT_MAGENTA}{'=' * 50}{Colors.RESET}")
            self.logger.info(f"{Colors.BRIGHT_MAGENTA}=== {title.upper()} {Colors.RESET}")
            self.logger.info(f"{Colors.BRIGHT_MAGENTA}{'=' * 50}{Colors.RESET}")
        else:
            self.logger.info(f"\n{'=' * 50}")
            self.logger.info(f"=== {title.upper()}")
            self.logger.info(f"{'=' * 50}")

# Function to create and configure a verbose logger
def get_logger(name, level=logging.INFO, enable_color=True, verbose_level=1):
    """
    Create and return a properly configured VerboseLogger.
    
    Args:
        name (str): Logger name
        level (int): Logging level (default: INFO)
        enable_color (bool): Whether to enable colored output (default: True)
        verbose_level (int): Verbosity level (1-3, with 3 being most verbose)
        
    Returns:
        VerboseLogger: Configured logger instance
    """
    # Set debug level based on environment variable if present
    env_debug = os.environ.get('DEBUG_LEVEL')
    if env_debug:
        try:
            level = getattr(logging, env_debug.upper())
        except (AttributeError, TypeError):
            # If invalid level, fall back to INFO
            pass
    
    # Get verbosity level from environment variable if present
    env_verbose = os.environ.get('VERBOSE_LEVEL')
    if env_verbose:
        try:
            verbose_level = int(env_verbose)
        except ValueError:
            # If invalid, use default
            pass
    
    # Determine color preference from environment
    env_color = os.environ.get('COLOR_OUTPUT', 'true').lower()
    enable_color = env_color not in ('false', 'no', '0', 'off')
    
    return VerboseLogger(name, level, enable_color, verbose_level)

# Example usage
if __name__ == "__main__":
    # Example of how to use the VerboseLogger
    logger = get_logger("test_module", verbose_level=3)
    
    logger.section("Logger Test")
    
    # Test different log levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    # Test task tracking
    task_id = "test-task-123"
    logger.task_start(task_id, "Example task to test logger functionality")
    
    # Test command execution tracking
    logger.command_start("ls -la", task_id)
    logger.command_result(
        "ls -la", 
        True, 
        "drwxr-xr-x 4 user user 4096 Jan 1 12:34 .\ndrwxr-xr-x 30 user user 4096 Jan 1 12:34 ..", 
        "", 
        0, 
        0.032
    )
    
    logger.command_start("cat /nonexistent/file", task_id)
    logger.command_result(
        "cat /nonexistent/file", 
        False, 
        "", 
        "cat: /nonexistent/file: No such file or directory", 
        1, 
        0.005
    )
    
    # Complete the task
    logger.task_complete(task_id, True, "All commands executed successfully")
