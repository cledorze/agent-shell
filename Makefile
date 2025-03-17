.PHONY: build-python run-python stop-python clean-python test-python

# Variables
DOCKER_COMPOSE = podman-compose -f docker-compose.python.yml
PROJECT_NAME = linux-agent-system

# Main commands for Python components
build-python:
	$(DOCKER_COMPOSE) build

run-python:
	$(DOCKER_COMPOSE) up -d

stop-python:
	$(DOCKER_COMPOSE) down

clean-python:
	$(DOCKER_COMPOSE) down -v

test-python:
	cd agent-system && python -m pytest
	cd knowledge-system && python -m pytest
