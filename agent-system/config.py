import os
import logging

# Configuration des variables d'environnement
KNOWLEDGE_SYSTEM_URL = os.environ.get('KNOWLEDGE_SYSTEM_URL', 'http://knowledge-system:8084')
COMMAND_EXECUTOR_URL = os.environ.get('COMMAND_EXECUTOR_URL', 'http://command-executor:8085')
VM_MANAGER_URL = os.environ.get('VM_MANAGER_URL', 'http://vm-manager:8083')
DATA_DIR = os.environ.get('DATA_DIR', '/app/data')
DRY_RUN = os.environ.get('DRY_RUN', 'true').lower() == 'true'
COMMAND_TIMEOUT = int(os.environ.get('COMMAND_TIMEOUT', '60'))
DEBUG_LEVEL = os.environ.get('DEBUG_LEVEL', 'INFO').upper()

frontend_dir = os.path.join(os.getcwd(), 'frontend')


# Configuration du logging
def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, DEBUG_LEVEL))
    return logger

logger = setup_logging()

# Fonction pour initialiser les composants
def initialize_components():
    from agents.enhanced_command_generator import EnhancedCommandGenerator
    from agents.execution_engine import ExecutionEngine
    from utils.state_manager import StateManager
    from utils.llm_service import LLMService
    
    command_generator = EnhancedCommandGenerator(knowledge_system_url=KNOWLEDGE_SYSTEM_URL)
    execution_engine = ExecutionEngine(dry_run=DRY_RUN, timeout=COMMAND_TIMEOUT)
    state_manager = StateManager(state_dir=os.path.join(DATA_DIR, 'states'))
    llm_service = LLMService(api_key=os.environ.get('OPENAI_API_KEY'))
    
    return command_generator, execution_engine, state_manager, llm_service
