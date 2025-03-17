import logging
from fastapi import HTTPException

from config import logger
from . import vm_manager
import command_handler
import task_processor

async def handle_chat_request(request, command_generator, execution_engine, state_manager, llm_service):
    """Process a chat request and generate a response."""
    # If task_id is provided, continue existing conversation
    if request.task_id:
        # Check if the task exists
        state = state_manager.get_state(request.task_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Task ID {request.task_id} not found")
        
        # Reset VM if requested
        if request.reset_vm:
            # Get VM ID from task state
            vm_id = state_manager.get_variable(request.task_id, "vm_id")
            if vm_id:
                await vm_manager.reset_vm(vm_id)
            else:
                # Create new VM for this task
                vm_data = await vm_manager.create_vm_for_task(request.task_id)
                if vm_data:
                    # Store VM info in state
                    state_manager.set_variable(request.task_id, "vm_id", vm_data["id"])
                    state_manager.set_variable(request.task_id, "vm_info", vm_data)
        
        # Add message to conversation history
        state_manager.add_conversation(request.task_id, "user", request.message)
        
        # Generate and execute commands if requested
        command_outputs = []
        if request.execute:
            # Generate execution plan
            logger.info(f"Generating commands for: {request.message}")
            plan = command_generator.generate_execution_plan(request.message)
            
            # Extract commands from the plan
            commands = []
            if plan and "steps" in plan:
                for step in plan["steps"]:
                    if "commands" in step:
                        commands.extend(step["commands"])
            
            # Execute commands
            if commands:
                vm_id = state_manager.get_variable(request.task_id, "vm_id")
                for command in commands:
                    if vm_id:
                        result = await command_handler.execute_command_on_vm(command, vm_id, request.task_id)
                    else:
                        result = await command_handler.execute_command_locally(command, execution_engine)
                    
                    command_outputs.append(result)
                    state_manager.record_command(request.task_id, command, result)
        
        # Generate response based on conversation history and command outputs
        conversation_history = state.conversation_history
        
        # Add command outputs to conversation context
        if command_outputs:
            outputs_text = "Command outputs:\n"
            for output in command_outputs:
                outputs_text += f"\nCommand: {output['command']}\n"
                if output.get("stdout"):
                    outputs_text += f"Output: {output['stdout']}\n"
                if output.get("stderr"):
                    outputs_text += f"Error: {output['stderr']}\n"
                outputs_text += f"Exit code: {output.get('exit_code', 'unknown')}\n"
            
            # Add to conversation history
            state_manager.add_conversation(request.task_id, "system", outputs_text)
            
            # Refresh conversation history
            conversation_history = state.conversation_history
        
        response = llm_service.generate_chat_response(conversation_history, request.message)
        
        # Add response to conversation history
        state_manager.add_conversation(request.task_id, "assistant", response)
        
        return {
            "response": response,
            "task_id": request.task_id,
            "status": state.status,
            "command_outputs": command_outputs
        }
    else:
        # Create a new task
        task_id = str(uuid.uuid4())
        
        # Initialize state
        state = state_manager.create_state(task_id, request.message)
        
        # Add initial message to conversation history
        state_manager.add_conversation(task_id, "user", request.message)
        
        # Generate initial response
        response = f"I'll help you with that task. I'm now processing: '{request.message}'"
        
        # Add response to conversation history
        state_manager.add_conversation(task_id, "assistant", response)
        
        return {
            "response": response,
            "task_id": task_id,
            "status": "initializing"
        }
