import logging
from fastapi import HTTPException

from config import logger
import vm_manager
import command_handler

async def process_task(task_id, task, execute, command_generator, execution_engine, state_manager):
    """Process a task and execute commands if requested."""
    try:
        # Update state to processing
        state = state_manager.get_state(task_id)
        state.status = "running"
        state_manager.save_state(state)
        
        # Generate execution plan
        logger.info(f"Task {task_id}: Generating execution plan")
        plan = command_generator.generate_execution_plan(task)
        
        # Update state with plan
        state_manager.update_plan(task_id, plan)
        
        if execute:
            # Extract commands from plan
            commands = []
            if plan and "steps" in plan:
                for step in plan["steps"]:
                    if "commands" in step:
                        commands.extend(step["commands"])
            
            # Execute commands
            if commands:
                logger.info(f"Task {task_id}: Executing {len(commands)} commands")
                
                # Get VM for task
                vm_id = state_manager.get_variable(task_id, "vm_id")
                
                for i, command in enumerate(commands):
                    logger.info(f"Task {task_id}: Executing command {i+1}/{len(commands)}")
                    
                    # Execute the command
                    if vm_id:
                        result = await command_handler.execute_command_on_vm(command, vm_id, task_id)
                    else:
                        result = await command_handler.execute_command_locally(command, execution_engine)
                    
                    # Store execution result
                    state_manager.record_command(task_id, command, result)
                    
                    # Update progress
                    state.current_step = i + 1
                    state_manager.save_state(state)
            
            # Mark as completed
            state_manager.complete_task(task_id, True)
        else:
            # Just mark as completed without execution
            state_manager.complete_task(task_id, True)
            
        logger.info(f"Task {task_id}: Processing completed")
            
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        state_manager.complete_task(task_id, False)
