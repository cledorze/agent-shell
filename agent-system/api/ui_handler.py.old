import os
from fastapi import HTTPException
from fastapi.responses import HTMLResponse

def serve_frontend():
    """Serve the frontend HTML."""
    # First check if we have a local index.html
    index_path = os.path.join(os.getcwd(), 'frontend', 'index.html')
    if os.path.exists(index_path):
        with open(index_path, 'r') as f:
            return f.read()

    # Otherwise, serve an embedded simple UI
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <!-- Contenu HTML intégré - Gardez le même contenu que dans votre fichier original -->
    </html>
    """
    return HTMLResponse(content=html_content)
