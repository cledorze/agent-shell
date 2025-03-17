import logging
import os
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CommandGenerator:
    """
    Generates Linux commands based on documentation and task requirements.
    """
    def __init__(self):
        self.common_commands = {
            "install": "sudo zypper install {package}",
            "update": "sudo zypper update {package}",
            "remove": "sudo zypper remove {package}",
            "service_enable": "sudo systemctl enable {service}",
            "service_start": "sudo systemctl start {service}",
            "service_status": "sudo systemctl status {service}",
            "firewall_open_port": "sudo firewall-cmd --permanent --add-port={port}/tcp",
            "firewall_reload": "sudo firewall-cmd --reload"
        }
        
        # Common configuration file paths
        self.config_paths = {
            "nginx": "/etc/nginx/nginx.conf",
            "nginx_sites": "/etc/nginx/conf.d/"
        }

    def generate_commands(self, task, documentation):
        """
        Generate appropriate commands for a task based on provided documentation.
        
        Args:
            task (str): Task description
            documentation (list): List of documentation items from Knowledge System
            
        Returns:
            list: List of generated commands
        """
        logger.info(f"Generating commands for task: {task}")
        
        # Extract relevant commands from task and documentation
        commands = []
        
        # Basic task parsing
        task_lower = task.lower()
        
        # Check if any documentation was provided
        if not documentation:
            logger.warning("No documentation provided for command generation")
            return []
            
        # Handle different types of tasks
        if "install" in task_lower:
            commands = self._handle_install_task(task_lower, documentation)
        elif "update" in task_lower:
            commands = self._handle_update_task(task_lower, documentation)
        elif "configure" in task_lower:
            commands = self._handle_configure_task(task_lower, documentation)
        elif "check" in task_lower or "monitor" in task_lower:
            commands = self._handle_monitoring_task(task_lower, documentation)
        
        # If no specific handler matched but we have some documentation, try general analysis
        if not commands and documentation:
            commands = self._analyze_task_general(task_lower, documentation)
        
        # Return the generated commands
        logger.info(f"Generated {len(commands)} commands")
        return commands
    
    def _handle_install_task(self, task_lower, documentation):
        """Handle tasks related to package installation."""
        commands = []
        
        # Extract the package name from the task
        for doc in documentation:
            if "install" in doc["content"].lower():
                # Check if the task mentions specific packages
                if "nginx" in task_lower and "nginx" in doc["content"].lower():
                    commands.append("sudo zypper install nginx")
                    # If task mentions boot/startup
                    if "boot" in task_lower or "start" in task_lower:
                        commands.append("sudo systemctl enable nginx")
                        commands.append("sudo systemctl start nginx")
                    # If the task might require opening ports
                    if "web" in task_lower or "nginx" in task_lower:
                        commands.append("sudo firewall-cmd --permanent --add-port=80/tcp")
                        commands.append("sudo firewall-cmd --reload")
                        
        return commands
    
    def _handle_update_task(self, task_lower, documentation):
        """Handle tasks related to system or package updates."""
        commands = []
        
        if "system" in task_lower:
            commands.append("sudo zypper update")
        else:
            # Try to extract specific package names
            package_match = re.search(r'update\s+(\w+)', task_lower)
            if package_match:
                package = package_match.group(1)
                commands.append(f"sudo zypper update {package}")
                
        return commands
    
    def _handle_configure_task(self, task_lower, documentation):
        """Handle tasks related to service configuration."""
        commands = []
        
        # Configuration tasks for specific services
        if "nginx" in task_lower:
            # Nginx configuration for static files
            if "static" in task_lower and "file" in task_lower:
                # Commands to configure Nginx for static file serving
                commands.append("# Install Nginx if not already installed")
                commands.append("sudo zypper install nginx")
                
                # Create a simple static site configuration
                commands.append("\n# Create a directory for static files")
                commands.append("sudo mkdir -p /var/www/static")
                
                # Set appropriate permissions
                commands.append("\n# Set appropriate permissions")
                commands.append("sudo chown -R nginx:nginx /var/www/static")
                commands.append("sudo chmod -R 755 /var/www/static")
                
                # Create a sample index.html file
                commands.append("\n# Create a sample index.html file")
                commands.append("echo '<html><body><h1>Static Files Server</h1></body></html>' | sudo tee /var/www/static/index.html")
                
                # Create Nginx configuration
                commands.append("\n# Create Nginx configuration for static files")
                commands.append("sudo cat > /etc/nginx/conf.d/static.conf << 'EOF'")
                commands.append("server {")
                commands.append("    listen 80;")
                commands.append("    server_name localhost;")
                commands.append("    ")
                commands.append("    location / {")
                commands.append("        root /var/www/static;")
                commands.append("        index index.html;")
                commands.append("    }")
                commands.append("}")
                commands.append("EOF")
                
                # Test configuration and restart Nginx
                commands.append("\n# Test Nginx configuration")
                commands.append("sudo nginx -t")
                commands.append("\n# Restart Nginx to apply changes")
                commands.append("sudo systemctl restart nginx")
                
                # Open firewall if needed
                commands.append("\n# Open firewall for HTTP traffic")
                commands.append("sudo firewall-cmd --permanent --add-service=http")
                commands.append("sudo firewall-cmd --reload")
            
            # Add other Nginx configuration scenarios as needed
            
        # Add other service configurations as needed
        
        return commands
    
    def _handle_monitoring_task(self, task_lower, documentation):
        """Handle tasks related to system monitoring."""
        commands = []
        
        if "memory" in task_lower:
            commands.append("free -h")
        elif "disk" in task_lower:
            commands.append("df -h")
        elif "process" in task_lower:
            commands.append("top")
        elif "network" in task_lower:
            commands.append("ss -tuln")
        
        return commands
    
    def _analyze_task_general(self, task_lower, documentation):
        """
        General task analysis when specific handlers don't match.
        This is a fallback method to extract relevant commands from documentation.
        """
        commands = []
        
        # Look for command patterns in documentation
        command_pattern = r"'(sudo\s+\w+.*?)'"  # Simple pattern to extract commands
        
        relevant_doc = None
        max_relevance = 0
        
        # Find the most relevant documentation
        for doc in documentation:
            # Simple relevance score based on word overlap
            doc_lower = doc["content"].lower()
            task_words = set(task_lower.split())
            doc_words = set(doc_lower.split())
            overlap = len(task_words.intersection(doc_words))
            
            if overlap > max_relevance:
                max_relevance = overlap
                relevant_doc = doc
        
        if relevant_doc:
            # Extract commands from the documentation
            doc_content = relevant_doc["content"]
            extracted_commands = re.findall(command_pattern, doc_content)
            
            if extracted_commands:
                commands.append("# Commands extracted from documentation:")
                commands.extend(extracted_commands)
            else:
                # If no commands found, provide general guidance
                commands.append("# No specific commands found in documentation.")
                commands.append("# Based on the task, you might want to:")
                
                # Add some general suggestions based on task keywords
                if "configure" in task_lower and "nginx" in task_lower:
                    commands.append("sudo vi /etc/nginx/nginx.conf  # Edit the main configuration file")
                    commands.append("sudo systemctl restart nginx  # Restart Nginx after configuration")
        
        return commands

# Example usage
if __name__ == "__main__":
    # This is for testing the module directly
    generator = CommandGenerator()
    task = "Configure Nginx to serve static files"
    docs = [
        {
            "title": "Installing and Configuring Nginx on OpenSUSE Tumbleweed",
            "content": "To install Nginx on OpenSUSE Tumbleweed, use the command: 'sudo zypper install nginx'. To enable and start the service: 'sudo systemctl enable nginx' and 'sudo systemctl start nginx'.",
            "source": "opensuse-docs"
        }
    ]
    commands = generator.generate_commands(task, docs)
    print(f"Task: {task}")
    print("Generated commands:")
    for cmd in commands:
        print(f"  - {cmd}")
