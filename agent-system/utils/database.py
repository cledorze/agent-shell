import sqlite3
import json
import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Database:
    """
    Simple SQLite database wrapper for persistent storage of tasks and results.
    """
    
    def __init__(self, db_path: str = None):
        """Initialize the database connection."""
        # Set default path if not provided
        if db_path is None:
            data_dir = os.environ.get('DATA_DIR', '/app/data')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'agent.db')
        
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
        # Initialize the database
        self._init_db()
    
    def _init_db(self):
        """Initialize the database connection and tables."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            # Enable column access by name
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            # Create tasks table if it doesn't exist
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                request_id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                created_at TEXT NOT NULL,
                processing_started TEXT,
                completed_at TEXT,
                details TEXT
            )
            ''')
            
            self.conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {str(e)}")
            if self.conn:
                self.conn.close()
            raise
    
    def _ensure_connection(self):
        """Ensure the database connection is active."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
    
    def create_task(self, request_id: str, task: str, priority: str, status: str) -> bool:
        """Create a new task in the database."""
        try:
            self._ensure_connection()
            now = datetime.now().isoformat()
            details = json.dumps({})
            
            self.cursor.execute(
                '''
                INSERT INTO tasks 
                (request_id, task, priority, status, created_at, details) 
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (request_id, task, priority, status, now, details)
            )
            self.conn.commit()
            logger.info(f"Task {request_id} created in database")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error creating task in database: {str(e)}")
            return False
    
    def update_task(self, request_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing task in the database."""
        try:
            self._ensure_connection()
            
            # Check if the task exists
            self.cursor.execute("SELECT 1 FROM tasks WHERE request_id = ?", (request_id,))
            if not self.cursor.fetchone():
                logger.warning(f"Task {request_id} not found in database")
                return False
            
            # Build the update query
            set_clauses = []
            params = []
            
            for key, value in updates.items():
                if key == 'details':
                    # Convert dictionary to JSON string
                    value = json.dumps(value)
                
                set_clauses.append(f"{key} = ?")
                params.append(value)
            
            # Add the request_id parameter
            params.append(request_id)
            
            # Execute the update
            query = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE request_id = ?"
            self.cursor.execute(query, params)
            self.conn.commit()
            
            logger.info(f"Task {request_id} updated in database")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error updating task in database: {str(e)}")
            return False
    
    def get_task(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a task from the database."""
        try:
            self._ensure_connection()
            
            self.cursor.execute("SELECT * FROM tasks WHERE request_id = ?", (request_id,))
            row = self.cursor.fetchone()
            
            if row:
                task = dict(row)
                # Parse the JSON stored in 'details'
                if 'details' in task and task['details']:
                    task['details'] = json.loads(task['details'])
                return task
            
            return None
        except sqlite3.Error as e:
            logger.error(f"Error getting task from database: {str(e)}")
            return None
    
    def list_tasks(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List tasks from the database."""
        try:
            self._ensure_connection()
            
            self.cursor.execute(
                "SELECT request_id, task, priority, status, created_at, completed_at FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?", 
                (limit, offset)
            )
            rows = self.cursor.fetchall()
            
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error listing tasks from database: {str(e)}")
            return []
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
