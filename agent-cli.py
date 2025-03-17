#!/usr/bin/env python3
# agent-cli.py

import requests
import json
import sys
import time
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Initialize rich console for colored output
console = Console()

# Default settings
API_URL = "http://localhost:8082"

def print_task_details(task):
    """Print task details in a nicely formatted panel"""
    task_id = task.get("request_id", "Unknown")
    status = task.get("status", "Unknown")
    task_desc = task.get("task", "No description")
    
    # Determine color based on status
    color = "green" if status == "completed" else "yellow" if status == "processing" else "red" if status == "failed" else "blue"
    
    # Create a panel with task information
    console.print(Panel(
        f"[bold]Task:[/bold] {task_desc}\n"
        f"[bold]Status:[/bold] [bold {color}]{status}[/bold {color}]\n"
        f"[bold]ID:[/bold] {task_id}",
        title=f"Task Details",
        border_style=color
    ))
    
    # If there's a message, print it
    if "message" in task:
        console.print(f"[bold]Message:[/bold] {task['message']}")

def submit_task(task_desc, execute=False):
    """Submit a task to the agent system"""
    url = f"{API_URL}/tasks"
    
    data = {
        "task": task_desc,
        "execute": execute
    }
    
    console.print(f"[bold blue]Submitting task:[/bold blue] {task_desc}")
    console.print(f"[bold blue]Execute commands:[/bold blue] {'Yes' if execute else 'No (dry run)'}")
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        task = response.json()
        
        print_task_details(task)
        
        # Return the task ID for further operations
        return task.get("request_id")
    
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]Error submitting task:[/bold red] {str(e)}")
        return None

def get_task_status(task_id):
    """Get status of a specific task"""
    url = f"{API_URL}/tasks/{task_id}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        task = response.json()
        
        print_task_details(task)
        return task
    
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]Error getting task status:[/bold red] {str(e)}")
        return None

def get_task_commands(task_id):
    """Get commands generated for a specific task"""
    url = f"{API_URL}/tasks/{task_id}/commands"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        result = response.json()
        
        # Print commands in a table
        commands = result.get("commands", [])
        
        if not commands:
            console.print("[yellow]No commands were generated for this task[/yellow]")
            return
        
        console.print(f"[bold green]Commands for task:[/bold green] {result.get('task', '')}")
        
        table = Table(show_header=True, header_style="bold")
        table.add_column("#")
        table.add_column("Command")
        
        for i, cmd in enumerate(commands, 1):
            table.add_row(str(i), cmd)
        
        console.print(table)
        
        return commands
    
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]Error getting task commands:[/bold red] {str(e)}")
        return None

def list_tasks():
    """List all tasks in the system"""
    url = f"{API_URL}/tasks"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        tasks = response.json().get("tasks", [])
        
        if not tasks:
            console.print("[yellow]No tasks found in the system[/yellow]")
            return
        
        # Create table of tasks
        table = Table(show_header=True, header_style="bold")
        table.add_column("ID")
        table.add_column("Task")
        table.add_column("Status", style="bold")
        table.add_column("Created")
        
        for task in tasks:
            status_style = "green" if task.get("status") == "completed" else "yellow" if task.get("status") == "processing" else "red"
            table.add_row(
                task.get("request_id", "Unknown")[:8] + "...",
                task.get("task", "Unknown"),
                f"[{status_style}]{task.get('status', 'Unknown')}[/{status_style}]",
                task.get("created_at", "Unknown")
            )
        
        console.print("[bold]Tasks in the system:[/bold]")
        console.print(table)
        
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]Error listing tasks:[/bold red] {str(e)}")

def check_health():
    """Check the health of the agent system"""
    url = f"{API_URL}/health"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        health = response.json()
        
        # Create a nicely formatted panel showing health status
        status = health.get("status", "unknown")
        color = "green" if status == "healthy" else "red"
        
        components = health.get("components", {})
        components_text = "\n".join(
            f"[bold]{name}:[/bold] [{color}]{status}[/{color}]" 
            for name, status in components.items()
        )
        
        console.print(Panel(
            f"[bold]Status:[/bold] [{color}]{status}[/{color}]\n\n{components_text}",
            title="Agent System Health",
            border_style=color
        ))
        
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]Error checking health:[/bold red] {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Command-line client for the Linux Agent System")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Health check command
    health_parser = subparsers.add_parser("health", help="Check the health of the agent system")
    
    # List tasks command
    list_parser = subparsers.add_parser("list", help="List all tasks")
    
    # Submit task command
    submit_parser = subparsers.add_parser("submit", help="Submit a new task")
    submit_parser.add_argument("task", help="Task description")
    submit_parser.add_argument("--execute", action="store_true", help="Execute the commands (default: dry run)")
    
    # Get task status command
    status_parser = subparsers.add_parser("status", help="Get status of a specific task")
    status_parser.add_argument("task_id", help="Task ID")
    
    # Get task commands command
    commands_parser = subparsers.add_parser("commands", help="Get commands for a specific task")
    commands_parser.add_argument("task_id", help="Task ID")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Execute the appropriate function based on the command
    if args.command == "health":
        check_health()
    elif args.command == "list":
        list_tasks()
    elif args.command == "submit":
        submit_task(args.task, args.execute)
    elif args.command == "status":
        get_task_status(args.task_id)
    elif args.command == "commands":
        get_task_commands(args.task_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
