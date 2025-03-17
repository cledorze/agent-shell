from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from agents.enhanced_command_generator import EnhancedCommandGenerator
from agents.execution_engine import ExecutionEngine
import logging
import os
import uuid
import requests
import json
from datetime import datetime

# Import our custom modules
from agents.command_generator import CommandGenerator
from agents.command_executor import CommandExecutor
from utils.database import Database

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Agent System")

# Initialize our components
command_generator = CommandGenerator()
command_generator = EnhancedCommandGenerator(knowledge_system_url=KNOWLEDGE_SYSTEM_URL)
#command_executor = CommandExecutor(
#    direct_execution=os.environ.get('DIRECT_EXECUTION', 'false').lower() == 'true',
#    dry_run=os.environ.get('DRY_RUN', 'true').lower() == 'true'
#)
execution_engine = ExecutionEngine(
    dry_run=os.environ.get('DRY_RUN', 'true').lower() == 'true',
    timeout=int(os.environ.get('COMMAND_TIMEOUT', '60'))
)
