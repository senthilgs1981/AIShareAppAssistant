from ast import Try
import os
import sys
import uvicorn
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from dotenv import load_dotenv

# Set up paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
AGENT_DIR = BASE_DIR  # Parent directory containing multi_tool_agent
# Set up DB path for sessions
#SESSION_DB_URL = f"sqlite:///{os.path.join(BASE_DIR, 'sessions.db')}"
# Create the FastAPI app using ADK's helper
app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    #session_db_kwargs=SESSION_DB_URL,
    allow_origins=["*"],  # In production, restrict this
    web=True,  # Enable the ADK Web UI
)
# Add custom endpoints
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/agent-info")
async def agent_info():
    """Provide agent information"""
    #Adding Exception Handling to trace the error
    try:
        from fin_assistant.agent import root_agent 
        return {
            "agent_name": root_agent.name,
            "description": root_agent.description,
            "model": root_agent.model,
            "tools": [t.__name__ for t in root_agent.tools]
        }
    except Exception as e:
        return {"error": str(e.message)}
    
    
if __name__ == "__main__":
    print("Starting FastAPI server...")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=9999, 
        reload=False
    )