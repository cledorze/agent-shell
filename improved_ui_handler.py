from fastapi.responses import HTMLResponse

def serve_frontend():
    """Serve a frontend HTML with better error handling."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Linux Agent System</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 40px;
                line-height: 1.6;
                color: #333;
                background-color: #f8f9fa;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: white;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1, h2 {
                color: #2c3e50;
            }
            .button {
                background-color: #3498db;
                color: white;
                padding: 10px 15px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            .button:hover {
                background-color: #2980b9;
            }
            textarea {
                width: 100%;
                height: 100px;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-bottom: 10px;
                font-family: inherit;
            }
            #response {
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                overflow-x: auto;
                white-space: pre-wrap;
                margin-top: 20px;
                border: 1px solid #ddd;
                display: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Linux Agent System</h1>
            <p>This interface allows you to interact with the Linux Agent System.</p>
            
            <h2>Execute a Task</h2>
            <textarea id="taskInput" placeholder="Enter a task description (e.g., 'Show system memory usage')"></textarea>
            <div style="margin-bottom: 10px;">
                <label>
                    <input type="checkbox" id="executeToggle"> Execute commands (use with caution)
                </label>
            </div>
            <button id="submitBtn" class="button">Submit Task</button>
            
            <pre id="response"></pre>
        </div>
        
        <script>
            document.getElementById('submitBtn').addEventListener('click', async function() {
                const taskInput = document.getElementById('taskInput');
                const executeToggle = document.getElementById('executeToggle');
                const responseDisplay = document.getElementById('response');
                
                const task = taskInput.value.trim();
                if (!task) {
                    alert('Please enter a task description');
                    return;
                }
                
                // Show response area and indicate loading
                responseDisplay.style.display = 'block';
                responseDisplay.textContent = 'Processing...';
                
                try {
                    // Send API request
                    const response = await fetch('/api/tasks', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            task: task,
                            execute: executeToggle.checked
                        })
                    });
                    
                    // Handle different response types
                    if (response.ok) {
                        // Try to parse as JSON
                        try {
                            const data = await response.json();
                            responseDisplay.textContent = JSON.stringify(data, null, 2);
                            
                            // If we have a task ID, poll for status after a delay
                            if (data.request_id) {
                                setTimeout(async () => {
                                    try {
                                        const statusResponse = await fetch(`/api/tasks/${data.request_id}`);
                                        if (statusResponse.ok) {
                                            const statusData = await statusResponse.json();
                                            responseDisplay.textContent = JSON.stringify(statusData, null, 2);
                                        } else {
                                            const errorText = await statusResponse.text();
                                            responseDisplay.textContent += '\\n\\nError fetching status: ' + errorText;
                                        }
                                    } catch (pollError) {
                                        responseDisplay.textContent += '\\n\\nError polling status: ' + pollError.message;
                                    }
                                }, 2000);
                            }
                        } catch (jsonError) {
                            // If JSON parsing fails, display as text
                            const textResponse = await response.text();
                            responseDisplay.textContent = 'Response (not JSON):\\n' + textResponse;
                        }
                    } else {
                        // Handle error responses
                        try {
                            // Try to parse error as JSON
                            const errorData = await response.json();
                            responseDisplay.textContent = 'Error ' + response.status + ':\\n' + 
                                JSON.stringify(errorData, null, 2);
                        } catch (e) {
                            // If not JSON, display as text
                            const errorText = await response.text();
                            responseDisplay.textContent = 'Error ' + response.status + ':\\n' + errorText;
                        }
                    }
                } catch (networkError) {
                    responseDisplay.textContent = 'Network error: ' + networkError.message;
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
