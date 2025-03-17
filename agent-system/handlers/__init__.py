# agent-system/handlers/__init__.py
# Export all handler modules
from .chat_handler import handle_chat_request
from .command_handler import execute_command_on_vm, execute_command_locally
from .task_processor import process_task
from .vm_manager import create_vm_for_task, reset_vm, get_vm_details
