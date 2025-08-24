import os
import sys
# Import dotenv for environment variable management
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

# Import required FastAPI components for building the API
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
# Import Pydantic for data validation and settings management
from pydantic import BaseModel
# Import OpenAI client for interacting with OpenAI's API
from openai import OpenAI
import asyncio
from typing import Optional, List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage

# Import memory management
try:
    from utils.memory import get_memory_manager
    print("✅ Successfully imported memory management")
except ImportError as e:
    print(f"❌ Failed to import memory management: {e}")
    get_memory_manager = None

# Add the src directory to the path so we can import our agentic system
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, src_path)

try:
    from utils.graph import agent_graph
    print("✅ Successfully imported agent graph builders")
except ImportError as e:
    print(f"❌ Failed to import agent graph builders: {e}")
    # Fallback imports if the above doesn't work
    utils_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utils'))
    sys.path.insert(0, utils_path)
    try:
        from graph import agent_graph
        print("✅ Successfully imported agent graph builders (fallback)")
    except ImportError as e2:
        print(f"❌ Fallback import also failed: {e2}")
        agent_graph = None

# Initialize FastAPI application with a title
app = FastAPI(title="S.A.V.E. API")

# Configure CORS (Cross-Origin Resource Sharing) middleware
# This allows the API to be accessed from different domains/origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from any origin
    allow_credentials=True,  # Allows cookies to be included in requests
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers in requests
)

# Initialize agent graphs
main_agent = None

try:
    print("🔄 Initializing agent graphs...")
    main_agent = agent_graph
    
    if main_agent:
        print("✅ All agent graphs initialized successfully")
    else:
        print("⚠️ Some agent graphs failed to initialize")
except Exception as e:
    print(f"❌ Failed to initialize agent graphs: {e}")
    main_agent = None

# Define the data model for chat requests using Pydantic
# This ensures incoming request data is properly validated
class ChatRequest(BaseModel):
    developer_message: str  # Message from the developer/system
    user_message: str      # Message from the user
    model: Optional[str] = None  # Optional model selection with default
    api_key: str          # OpenAI API key for authentication

# Define data model for agent chat requests
class AgentChatRequest(BaseModel):
    message: str  # User message to send to the agent
    session_id: Optional[str] = None  # Session ID is no longer used, kept for compatibility

# Define response models
class AgentResponse(BaseModel):
    response: str



# Define the main chat endpoint that handles POST requests
@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        # Initialize OpenAI client with the provided API key
        client = OpenAI(api_key=request.api_key)
        
        # Use environment variable as default if no model provided
        model_to_use = request.model if request.model else os.environ.get("OPENAI_LIGHT_MODEL", "gpt-4.1-mini")
        
        # Create an async generator function for streaming responses
        async def generate():
            # Create a streaming chat completion request
            stream = client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "developer", "content": request.developer_message},
                    {"role": "user", "content": request.user_message}
                ],
                stream=True  # Enable streaming response
            )
            
            # Yield each chunk of the response as it becomes available
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        # Return a streaming response to the client
        return StreamingResponse(generate(), media_type="text/plain")
    
    except Exception as e:
        # Handle any errors that occur during processing
        raise HTTPException(status_code=500, detail=str(e))

# New agent chat endpoint that uses the agentic system
@app.post("/api/agent/chat", response_model=AgentResponse)
async def agent_chat(request: AgentChatRequest):
    """
    Chat with the intelligent S.A.V.E. (Simple Autonomous Validation Engine) that can:
    - Extract and validate UPC codes
    - Search product databases (USDA FDC)
    - Perform web searches for food information
    - Maintain conversation memory for workflow continuity
    """
    if main_agent is None:
        raise HTTPException(status_code=500, detail="Agent system not initialized")
    
    if get_memory_manager is None:
        raise HTTPException(status_code=500, detail="Memory management not available")
    
    try:
        print(f"🔄 Processing agent chat request: {request.message[:50]}...")
        
        # Clean up expired sessions
        memory_manager = get_memory_manager()
        memory_manager.cleanup_expired_sessions()
        
        # Create a human message from the user input
        user_message = HumanMessage(content=request.message)
        
        # Get conversation context with memory management (without adding user message yet)
        conversation_messages = memory_manager.get_conversation_context()
        print(f"📝 Conversation context has {len(conversation_messages)} messages")
        
        # Add the user message to the conversation context for processing
        conversation_messages.append(user_message)
        
        print("🚀 Invoking agent...")
        # Invoke the agent with the full conversation context
        result = main_agent.invoke({"messages": conversation_messages})
        
        # Extract the response from the agent's output
        agent_response = result["messages"][-1].content if result["messages"] else "No response generated"
        print(f"✅ Agent response generated: {len(agent_response)} chars")
        
        # Add both user message and agent response to memory after successful processing
        memory_manager.add_message(message=user_message)
        if result["messages"]:
            memory_manager.add_message(message=result["messages"][-1])
        
        return AgentResponse(
            response=agent_response
        )
        
    except Exception as e:
        print(f"❌ Agent chat error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


# SSE endpoint for agent chat with progress tracking (GET)
@app.get("/api/agent/chat/stream-sse")
async def agent_chat_stream_sse(message: str):
    """
    SSE version of agent chat with real-time progress updates using GET
    """
    if main_agent is None:
        raise HTTPException(status_code=500, detail="Agent system not initialized")
    
    if get_memory_manager is None:
        raise HTTPException(status_code=500, detail="Memory management not available")
    
    async def generate():
        try:
            import json
            print(f"🔄 Starting SSE stream for message: {message[:50]}...")
            
            # Clean up expired sessions
            memory_manager = get_memory_manager()
            memory_manager.cleanup_expired_sessions()
            
            # Create a human message from the user input
            user_message = HumanMessage(content=message)
            
            # Get conversation context with memory management (without adding user message yet)
            conversation_messages = memory_manager.get_conversation_context()
            print(f"📝 Conversation context has {len(conversation_messages)} messages")
            
            # Add the user message to the conversation context for processing
            conversation_messages.append(user_message)
            
            final_response_content = None
            
            print("🚀 Starting agent stream...")
            # Use LangGraph's streaming capability to track actual node execution
            for event in main_agent.stream({"messages": conversation_messages}):
                print(f"📡 Stream event: {list(event.keys())}")  # Debug logging
                
                # Handle different types of events from the graph
                for node_name, node_data in event.items():
                    if node_name == "__start__":
                        progress_msg = json.dumps({"type": "progress", "step": "Starting analysis", "node": "start"})
                        yield f"data: {progress_msg}\n\n"
                    
                    elif node_name == "assistant":
                        progress_msg = json.dumps({"type": "progress", "step": "AI agent analyzing request", "node": "assistant"})
                        yield f"data: {progress_msg}\n\n"
                        
                        # Capture the assistant's response for final output
                        if "messages" in node_data and node_data["messages"]:
                            last_message = node_data["messages"][-1]
                            if hasattr(last_message, 'content'):
                                final_response_content = last_message.content
                                print(f"💬 Assistant response captured: {len(final_response_content)} chars")
                    
                    elif node_name == "tools":
                        # Extract actual tool information from the node data
                        progress_msg = json.dumps({"type": "progress", "step": "Executing tools", "node": "tools"})
                        yield f"data: {progress_msg}\n\n"
                        
                        # Try to identify which tools were called
                        if "messages" in node_data and node_data["messages"]:
                            for msg in node_data["messages"]:
                                if hasattr(msg, 'name'):
                                    tool_name = msg.name.lower()
                                    if 'upc' in tool_name:
                                        progress_msg = json.dumps({"type": "progress", "step": "Extracting and validating UPC codes", "node": "tools"})
                                        yield f"data: {progress_msg}\n\n"
                                    elif 'usda' in tool_name:
                                        progress_msg = json.dumps({"type": "progress", "step": "Searching USDA Food Database", "node": "tools"})
                                        yield f"data: {progress_msg}\n\n"
                                    elif 'openfoodfacts' in tool_name:
                                        progress_msg = json.dumps({"type": "progress", "step": "Searching OpenFoodFacts database", "node": "tools"})
                                        yield f"data: {progress_msg}\n\n"
                                    elif 'tavily' in tool_name:
                                        progress_msg = json.dumps({"type": "progress", "step": "Searching the web for food information", "node": "tools"})
                                        yield f"data: {progress_msg}\n\n"

                    
                    elif node_name == "__end__":
                        progress_msg = json.dumps({"type": "progress", "step": "Preparing final response", "node": "end"})
                        yield f"data: {progress_msg}\n\n"
                        
                        # Get final response from end event if not already captured
                        if not final_response_content and "messages" in node_data and node_data["messages"]:
                            last_message = node_data["messages"][-1]
                            if hasattr(last_message, 'content'):
                                final_response_content = last_message.content
                                print(f"🎯 Final response from end event: {len(final_response_content)} chars")
            
            print(f"✅ Stream completed, final response length: {len(final_response_content) if final_response_content else 0}")
            
            # Send the final response
            if final_response_content:
                # Add both user message and agent response to memory after successful processing
                memory_manager.add_message(message=user_message)
                if final_response_content:
                    ai_message = AIMessage(content=final_response_content)
                    memory_manager.add_message(message=ai_message)
                
                final_msg = json.dumps({"type": "response", "content": final_response_content})
                yield f"data: {final_msg}\n\n"
            else:
                error_msg = json.dumps({"type": "error", "content": "No response generated"})
                yield f"data: {error_msg}\n\n"
                
        except Exception as e:
            import json
            print(f"❌ Streaming error: {e}")
            import traceback
            traceback.print_exc()
            error_response = json.dumps({"type": "error", "content": f"Error: {str(e)}"})
            yield f"data: {error_response}\n\n"
    
    return StreamingResponse(
        generate(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*", 
            "Access-Control-Allow-Methods": "*",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )







# Get agent capabilities endpoint
@app.get("/api/agent/capabilities")
async def get_agent_capabilities():
    """
    Get information about what the agent can do
    """
    memory_stats = {}
    if get_memory_manager:
        memory_manager = get_memory_manager()
        memory_stats = memory_manager.get_session_stats()
    
    return {
        "capabilities": [
            "UPC code extraction and validation",
            "Example database lookup (priority)",
            "USDA Food Data Central integration",
            "OpenFoodFacts product database search",
            "Web search for food information",
            "Nutritional data lookup",
            "Product comparison and analysis",
            "Conversation memory for workflow continuity"
        ],
        "tools": [
            "UPC Extraction Tool",
            "UPC Validator Tool", 
            "UPC Check Digit Calculator",
            "Example Database Tool",
            "OpenFoodFacts Tool",
            "USDA FDC Tool",
            "Tavily Search Tool"
        ],
        "status": "online" if main_agent is not None else "offline",
        "memory": memory_stats
    }


# Reset session endpoint
@app.post("/api/agent/reset-session")
async def reset_session():
    """
    Reset the single session, clearing all conversation memory
    """
    if get_memory_manager is None:
        raise HTTPException(status_code=500, detail="Memory management not available")
    
    try:
        memory_manager = get_memory_manager()
        memory_manager.reset_session()
        return {"message": "Session reset successfully", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset session: {str(e)}")


# Define a health check endpoint to verify API status
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "agent_status": "online" if main_agent is not None else "offline"
    }

# Entry point for running the application directly
if __name__ == "__main__":
    import uvicorn
    # Start the server on all network interfaces (0.0.0.0) on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
