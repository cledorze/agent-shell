from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import os
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Knowledge System")

# Define Pydantic models for request and response validation
class SearchQuery(BaseModel):
    query: str
    limit: Optional[int] = 5

class DocumentResult(BaseModel):
    title: str
    content: str
    relevance: float
    source: str

class SearchResponse(BaseModel):
    results: List[DocumentResult]
    query: str
    total_results: int

class DocumentationItem(BaseModel):
    title: str
    content: str
    source: str
    tags: List[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

# Path for persistent storage
DATA_DIR = os.environ.get('DATA_DIR', '/app/data')
os.makedirs(DATA_DIR, exist_ok=True)
DOCS_FILE = os.path.join(DATA_DIR, 'opensuse_docs.json')

# Initialize with comprehensive documentation database
opensuse_docs = [
    {
        "title": "Installing and Configuring Nginx on OpenSUSE Tumbleweed",
        "content": "To install Nginx on OpenSUSE Tumbleweed, use the command: 'sudo zypper install nginx'. To enable and start the service: 'sudo systemctl enable nginx' and 'sudo systemctl start nginx'. You can verify the installation with 'systemctl status nginx'. The default web root is located at /srv/www/htdocs/.",
        "source": "opensuse-docs",
        "tags": ["nginx", "web server", "installation", "configuration", "service"],
        "created_at": "2025-03-01T00:00:00Z",
        "updated_at": "2025-03-01T00:00:00Z"
    },
    {
        "title": "Package Management with Zypper in OpenSUSE Tumbleweed",
        "content": "Zypper is the command-line interface to ZYpp package management engine in OpenSUSE Tumbleweed. Basic commands include: 'zypper install <package>' to install packages, 'zypper remove <package>' to remove packages, 'zypper update' to update all packages, 'zypper search <keyword>' to search for packages, and 'zypper info <package>' to get detailed information about a package. Use 'zypper lr' to list configured repositories.",
        "source": "opensuse-docs",
        "tags": ["zypper", "package management", "repositories", "installation", "update"],
        "created_at": "2025-03-01T00:00:00Z",
        "updated_at": "2025-03-01T00:00:00Z"
    },
    # Other documentation entries remain the same...
    {
        "title": "Network Configuration in OpenSUSE Tumbleweed",
        "content": "Network configuration in OpenSUSE Tumbleweed can be managed using several methods: 'ip addr' to show network interfaces, 'ip route' to display routing table, 'nmcli' for NetworkManager CLI control, 'hostnamectl set-hostname <name>' to set the hostname, and editing files in /etc/sysconfig/network/. You can also use YaST for graphical network configuration. DNS settings are in /etc/resolv.conf.",
        "source": "opensuse-docs",
        "tags": ["network", "interfaces", "configuration", "ip", "dns", "hostname"],
        "created_at": "2025-03-01T00:00:00Z",
        "updated_at": "2025-03-01T00:00:00Z"
    },
    {
        "title": "System Monitoring in OpenSUSE Tumbleweed",
        "content": "Monitor your OpenSUSE Tumbleweed system with various tools: 'top' or 'htop' for process monitoring, 'free -h' for memory usage, 'df -h' for disk usage, 'netstat -tuln' or 'ss -tuln' for network connections, 'iotop' for disk I/O, and 'journalctl' to view system logs. For graphical monitoring, install and use 'gnome-system-monitor' or 'ksysguard'.",
        "source": "opensuse-docs",
        "tags": ["monitoring", "performance", "processes", "memory", "disk", "network"],
        "created_at": "2025-03-01T00:00:00Z",
        "updated_at": "2025-03-01T00:00:00Z"
    }
]

# Save initial documentation to file if it doesn't exist
def init_documentation():
    global opensuse_docs  # Move global declaration to the beginning of the function
    
    if not os.path.exists(DOCS_FILE):
        with open(DOCS_FILE, 'w') as f:
            json.dump(opensuse_docs, f, indent=2)
        logger.info(f"Initialized documentation database with {len(opensuse_docs)} entries")
    else:
        # Load existing documentation
        try:
            with open(DOCS_FILE, 'r') as f:
                opensuse_docs = json.load(f)
            logger.info(f"Loaded {len(opensuse_docs)} documentation entries from {DOCS_FILE}")
        except Exception as e:
            logger.error(f"Error loading documentation: {str(e)}")

# Initialize documentation on startup
init_documentation()

@app.get("/")
async def root():
    return {"status": "Knowledge System operational", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "doc_count": len(opensuse_docs),
        "storage": os.path.exists(DOCS_FILE)
    }

@app.post("/search", response_model=SearchResponse)
async def search_documentation(query: SearchQuery):
    """
    Search for relevant documentation based on a query.
    """
    logger.info(f"Search query: {query.query}")
    
    # Simple keyword search function (in a real implementation, this would use vector search)
    def search_relevance(doc, query_terms):
        query_terms = [term.lower() for term in query_terms]
        content = doc["content"].lower()
        title = doc["title"].lower()
        tags = [tag.lower() for tag in doc.get("tags", [])]
        
        # Calculate a simple relevance score based on keyword occurrences
        score = 0
        for term in query_terms:
            if term in title:
                score += 0.5  # Title matches are weighted higher
            if term in content:
                score += 0.3
            if any(term in tag for tag in tags):
                score += 0.2  # Tag matches
        
        return score
    
    # Split query into terms
    query_terms = query.query.split()
    
    # Calculate relevance for each document
    results = []
    for doc in opensuse_docs:
        relevance = search_relevance(doc, query_terms)
        if relevance > 0:
            results.append({
                "title": doc["title"],
                "content": doc["content"],
                "relevance": round(relevance, 2),
                "source": doc["source"]
            })
    
    # Sort by relevance (highest first)
    results.sort(key=lambda x: x["relevance"], reverse=True)
    
    # Limit results
    results = results[:query.limit]
    
    return {
        "results": results,
        "query": query.query,
        "total_results": len(results)
    }

@app.get("/documentation/{topic}")
async def get_documentation(topic: str):
    """
    Get comprehensive documentation for a specific topic.
    """
    # Simple lookup (would be more sophisticated in a real implementation)
    for doc in opensuse_docs:
        if topic.lower() in doc["title"].lower():
            return {
                "topic": topic,
                "content": doc["content"],
                "source": doc["source"],
                "tags": doc.get("tags", []),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at")
            }
    
    raise HTTPException(status_code=404, detail="Documentation not found for this topic")

@app.get("/documentation")
async def list_documentation():
    """
    List all available documentation topics.
    """
    return {
        "topics": [{"title": doc["title"], "tags": doc.get("tags", [])} for doc in opensuse_docs],
        "count": len(opensuse_docs)
    }

@app.post("/documentation")
async def add_documentation(doc: DocumentationItem):
    """
    Add new documentation to the knowledge base.
    """
    # Set timestamps
    now = datetime.now().isoformat()
    new_doc = doc.dict()
    new_doc["created_at"] = now
    new_doc["updated_at"] = now
    
    # Add to the in-memory database
    opensuse_docs.append(new_doc)
    
    # Save to file
    try:
        with open(DOCS_FILE, 'w') as f:
            json.dump(opensuse_docs, f, indent=2)
        logger.info(f"Added new documentation: {doc.title}")
    except Exception as e:
        logger.error(f"Error saving documentation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save documentation")
    
    return {"status": "success", "message": "Documentation added", "doc_id": len(opensuse_docs) - 1}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8084, reload=True)
