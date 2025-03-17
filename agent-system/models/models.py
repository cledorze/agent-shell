from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class TaskRequest(BaseModel):
    task: str
    priority: Optional[str] = "normal"
    timeout: Optional[int] = 300
    execute: Optional[bool] = False
    reset_vm: Optional[bool] = False

class ChatRequest(BaseModel):
    message: str
    execute: Optional[bool] = False
    task_id: Optional[str] = None
    reset_vm: Optional[bool] = False

class ChatResponse(BaseModel):
    response: str
    task_id: Optional[str] = None
    status: Optional[str] = None
    command_outputs: Optional[List[Dict[str, Any]]] = None

class TaskStatus(BaseModel):
    request_id: str
    status: str
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class ResetVMRequest(BaseModel):
    force: Optional[bool] = False
