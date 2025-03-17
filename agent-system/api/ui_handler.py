import os
from fastapi.responses import HTMLResponse

def serve_frontend():
    """Serve the frontend HTML."""
    # Create a simple but functional HTML dashboard
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Linux Agent System</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f8f9fa;
            }
            header {
                background-color: #2c3e50;
                color: white;
                padding: 1rem;
                border-radius: 5px;
                margin-bottom: 20px;
            }
            h1, h2, h3 {
                margin-top: 0;
            }
            .card {
                background: white;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                padding: 20px;
                margin-bottom: 20px;
            }
            .form-group {
                margin-bottom: 15px;
            }
            input, textarea {
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                box-sizing: border-box;
                font-family: inherit;
            }
            button {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 4px;
                cursor: pointer;
            }
            button:hover {
                background-color: #2980b9;
            }
            #response {
                white-space: pre-wrap;
                background-color: #f0f0f0;
                padding: 15px;
                border-radius: 4px;
                margin-top: 10px;
                display: none;
            }
            .system-status {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 20px;
            }
            .status-item {
                background: white;
                border-radius: 5px;
                padding: 10px;
                flex: 1;
                min-width: 150px;
                text-align: center;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .status-healthy {
                color: #27ae60;
            }
            .status-unhealthy {
                color: #e74c3c;
            }
        </style>
    </head>
    <body>
        <header>
            <h1>Linux Agent System</h1>
            <p>Manage and configure OpenSUSE Tumbleweed Linux machines</p>
        </header>

        <div class="card">
            <h2>System Status</h2>
            <div class="system-status" id="systemStatus">
                <div class="status-item">
                    <h3>Agent System</h3>
                    <p class="status-healthy">Healthy</p>
                </div>
                <div class="status-item">
                    <h3>Knowledge System</h3>
                    <p class="status-healthy">Healthy</p>
                </div>
                <div class="status-item">
                    <h3>Command Executor</h3>
                    <p class="status-unhealthy">Unhealthy</p>
                </div>
                <div class="status-item">
                    <h3>VM Manager</h3>
                    <p class="status-unhealthy">Unhealthy</p>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Execute Command</h2>
            <div class="form-group">
                <label for="command">Enter your command or instruction:</label>
                <textarea id="command" rows="3" placeholder="Example: Show system memory usage"></textarea>
            </div>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="executeCommands"> Execute commands (use with caution)
                </label>
            </div>
            <button id="submitCommand">Submit</button>
            <pre id="response"></pre>
        </div>

        <div class="card">
            <h2>API Documentation</h2>
            <p>Access the full API documentation at <a href="/docs">/docs</a></p>
            <p>Check system health at <a href="/health">/health</a></p>
        </div>

        <script>
            // Load system status on page load
            window.addEventListener('DOMContentLoaded', async () => {
                try {
                    const response = await fetch('/health');
                    const data = await response.json();
                    
                    // Update status indicators
                    const statusDiv = document.getElementById('systemStatus');
                    statusDiv.innerHTML = '';
                    
                    for (const [name, status] of Object.entries(data.components)) {
                        const statusClass = status === 'healthy' ? 'status-healthy' : 'status-unhealthy';
                        const statusItem = document.createElement('div');
                        statusItem.className = 'status-item';
                        statusItem.innerHTML = `
                            <h3>${name.charAt(0).toUpperCase() + name.slice(1).replace('_', ' ')}</h3>
                            <p class="${statusClass}">${status}</p>
                        `;
                        statusDiv.appendChild(statusItem);
                    }
                } catch (error) {
                    console.error('Error fetching system status:', error);
                }
            });

            // Handle command submission
            document.getElementById('submitCommand').addEventListener('click', async () => {
                const command = document.getElementById('command').value.trim();
                const executeCommands = document.getElementById('executeCommands').checked;
                const responseElement = document.getElementById('response');
                
                if (!command) return;
                
                responseElement.style.display = 'block';
                responseElement.textContent = 'Processing...';
                
                try {
                    const response = await fetch('/api/tasks', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            task: command,
                            execute: executeCommands,
                        }),
                    });
                    
                    const data = await response.json();
                    responseElement.textContent = JSON.stringify(data, null, 2);
                    
                    // If we have a task ID, poll for updates
                    if (data.request_id) {
                        setTimeout(async () => {
                            try {
                                const statusResponse = await fetch(`/api/tasks/${data.request_id}`);
                                const statusData = await statusResponse.json();
                                responseElement.textContent = JSON.stringify(statusData, null, 2);
                            } catch (error) {
                                console.error('Error polling task status:', error);
                            }
                        }, 2000);
                    }
                } catch (error) {
                    responseElement.textContent = `Error: ${error.message}`;
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
