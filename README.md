# Linux Agent System

Autonomous agent system for managing and configuring OpenSUSE Tumbleweed Linux machines.

## Features

- Process natural language instructions for system administration
- VM orchestration with automatic reset capabilities
- Contextual documentation search for precise execution
- Secure remote command execution via ngrok

## Architecture

The system consists of several components:

1. API Gateway (Go) - Entry point for requests
2. Orchestrator (Go) - Agent work coordination
3. Agent System (Python) - Intelligent task processing
4. VM Manager (Go) - Virtual machine lifecycle management
5. Command Executor (Rust) - Secure command execution
6. Knowledge System - Information storage and retrieval

## Installation

```bash
# Clone the repository
git clone https://github.com/user/linux-agent-system.git
cd linux-agent-system

# Configure environment variables
cp .env.example .env
nano .env  # Modify according to your needs

# Build and start services
make build
make run
```

## Usage

```bash
# Example of sending an instruction
curl -X POST http://localhost:8080/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"task": "Install nginx and configure it to start at boot"}'
```

## Development

```bash
# Run tests
make test

# Build a specific component
make build-api-gateway
```

## License

MIT
