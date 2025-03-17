# Add these lines to properly export models:
from .models import TaskRequest, ChatRequest, TaskStatus, ChatResponse, ResetVMRequest

# Define which symbols to expose:
__all__ = ['TaskRequest', 'ChatRequest', 'TaskStatus', 'ChatResponse', 'ResetVMRequest']
