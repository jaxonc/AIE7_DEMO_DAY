import os
from langgraph.graph import END
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing import Annotated
from typing_extensions import TypedDict
from .model import get_model
from .upc_validator import UPCValidatorTool, UPCCheckDigitCalculatorTool
from .openfoodfacts_tool import OpenFoodFactsTool
from .usda_fdc_tool import USDAFoodDataCentralTool
from .extraction_tool import UPCExtractionTool
from .example_database_tool import ExampleDatabaseTool
from .prompts import get_upc_assistant_prompt, get_upc_assistant_regeneration_prompt, get_validation_node_prompt, get_context_aware_regeneration_prompt
try:
    from langchain_tavily import TavilySearchResults
except ImportError:
    from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.prebuilt import ToolNode
from langgraph.graph import START, StateGraph
from IPython.display import Image, display
from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
# Import dotenv for environment variable management
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def response_validation_node(state: dict) -> dict:
    """
    Validate response completeness and quality for SAVE product information queries.
    
    For comprehensive product queries: Ensures all 7 priority attributes are included when applicable.
    For specific queries: Validates that the response adequately answers within system capabilities.
    For beverages: Ensures juice content is always included.
    """
    # If we've exceeded loop limit, short-circuit with END decision marker
    if len(state["messages"]) > 30:
        return {"messages": [AIMessage(content="VALIDATION:END")]}
    
    # Find the current user query (not the first message in conversation)
    current_query = None
    final_response = state["messages"][-1]
    
    # Look for the most recent human message (user query)
    for message in reversed(state["messages"][:-1]):  # Exclude the final response
        if hasattr(message, 'type') and message.type == "human":
            current_query = message
            break
    
    # If no human message found, use the first message as fallback
    if current_query is None:
        current_query = state["messages"][0]
    
    print(f"🔍 Validating response for query: {current_query.content[:50]}...")
    
    # Skip validation for non-product queries (off-topic redirections)
    if "Simple Autonomous Verification Engine" in final_response.content and "specialized resources" in final_response.content:
        print("✅ Skipping validation - off-topic query redirected")
        return {"messages": [AIMessage(content="VALIDATION:PASS")]}
    
    # Skip validation for non-product queries (like asking about Batman)
    current_query_lower = current_query.content.lower()
    non_product_indicators = [
        "batman", "superhero", "character", "movie", "actor", "weather", "politics", 
        "history", "geography", "math", "science", "philosophy", "religion", "sports",
        "music", "art", "literature", "who is", "what is the weather", "tell me about"
    ]
    
    is_non_product_query = any(indicator in current_query_lower for indicator in non_product_indicators)
    
    if is_non_product_query:
        print("✅ Skipping validation - non-product query detected")
        return {"messages": [AIMessage(content="VALIDATION:PASS")]}
    
    # Skip validation if example database found a product
    for message in state["messages"]:
        if hasattr(message, 'content') and message.content:
            if "Product found in Example Database" in message.content:
                print("✅ Skipping validation - product found in example database")
                return {"messages": [AIMessage(content="VALIDATION:PASS")]}
    
    validation_prompt = get_validation_node_prompt()

    # Use environment variable for validation model, defaulting to a lightweight model
    validation_model_name = os.environ.get("ANTHROPIC_LIGHT_MODEL", "claude-3-haiku-20240307")
    validation_model = get_model(validation_model_name)
    
    validation_template = PromptTemplate.from_template(validation_prompt)
    validation_chain = validation_template | validation_model | StrOutputParser()
    
    print(f"🔍 Running validation on response: {len(final_response.content)} chars")
    validation_response = validation_chain.invoke({
        "initial_query": current_query.content,
        "final_response": final_response.content,
    })
    
    print(f"🔍 Validation response: {validation_response[:100]}...")
    
    # Determine validation result - simplified since specific context is in the message
    validation_lower = validation_response.lower()
    
    if "pass" in validation_lower:
        decision = "PASS"
        print("✅ Validation PASSED")
        return {"messages": [AIMessage(content="VALIDATION:PASS")]}
    else:
        # Any failure - pass the detailed validation response to the assistant
        print(f"❌ Validation FAILED: {validation_response}")
        return {"messages": [AIMessage(content=f"VALIDATION:FAIL - {validation_response}")]}


def should_continue_after_validation(state: dict) -> str:
    """
    Determine if response should be regenerated based on validation results.
    
    Returns:
        "assistant": Response failed validation, route back to assistant for fixing
        "end": Response passed validation or max attempts reached
    """
    if len(state["messages"]) > 30:
        return "end"
    
    last_message = state["messages"][-1]
    
    if hasattr(last_message, 'content') and "VALIDATION:" in last_message.content:
        if "VALIDATION:PASS" in last_message.content:
            return "end"
        elif "VALIDATION:END" in last_message.content:
            return "end"
        else:
            # Any FAIL result routes back to assistant
            return "assistant"
    
    return "end"


def build_graph(model_name: str = None, display_graph: bool = False, debug_extraction: bool = False):
    try:
        # Use environment variable as default if no model_name provided
        if model_name is None:
            model_name = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        
        print(f"🤖 Initializing main model: {model_name}")
        # Initialize main model for the agent (keeps Sonnet 4 for complex reasoning)
        model = get_model(model_name)
        
        # Initialize a separate, lighter model specifically for the extraction tool
        # Using Haiku for cost efficiency since extraction is a simple pattern matching task
        extraction_model_name = os.environ.get("ANTHROPIC_LIGHT_MODEL", "claude-3-haiku-20240307")
        print(f"🤖 Initializing extraction model: {extraction_model_name}")
        extraction_model = get_model(extraction_model_name)
        
        print("✅ Models initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize models: {e}")
        raise
    
    # Initialize tools with error handling
    tool_belt = []
    
    # Add extraction tool first (priority)
    upc_extraction_tool = UPCExtractionTool(model=extraction_model, debug=debug_extraction)
    tool_belt.append(upc_extraction_tool)
    
    # Add validation tools
    upc_validator = UPCValidatorTool()
    upc_check_digit_calculator = UPCCheckDigitCalculatorTool()
    tool_belt.extend([upc_validator, upc_check_digit_calculator])
    
    # Add example database tool
    example_database_tool = ExampleDatabaseTool()
    tool_belt.append(example_database_tool)
    
    # Add database tools with API key checks
    tool_belt.append(OpenFoodFactsTool())  # No API key required
    
    # Check USDA API key
    usda_api_key = os.environ.get("USDA_API_KEY")
    if usda_api_key:
        tool_belt.append(USDAFoodDataCentralTool())
        print("✅ USDA FDC tool initialized")
    else:
        print("⚠️ USDA_API_KEY not found - USDA database functionality disabled")
    
    # Add Tavily search tool with API key check
    try:
        tavily_api_key = os.environ.get("TAVILY_API_KEY")
        if tavily_api_key:
            tavily_tool = TavilySearchResults(max_results=5)
            tool_belt.append(tavily_tool)
            print("✅ Tavily search tool initialized")
        else:
            print("⚠️ TAVILY_API_KEY not found - web search functionality disabled")
    except Exception as e:
        print(f"⚠️ Failed to initialize Tavily tool: {e}")
    
    print(f"🔧 Initialized {len(tool_belt)} tools")

    model = model.bind_tools(tool_belt)
    
    class GraphState(TypedDict):
        messages: Annotated[list[AnyMessage], add_messages]

    # Define the function that determines whether to continue or not
    def should_continue(state: GraphState):
        messages = state["messages"]
        last_message = messages[-1]
        
        # Check if the last message has tool calls
        if last_message.tool_calls:
            return "tools"
        
        # Check if the last message is from a tool (tool result)
        if hasattr(last_message, 'name') and last_message.name:
            # This is a tool result - check if it's from example database
            if last_message.name == "example_database_lookup":
                if "Product found in Example Database" in last_message.content:
                    print("✅ Example database found product - skipping validation")
                    return "end"
        
        # Check if the last message contains tool results from example database
        if hasattr(last_message, 'content') and last_message.content:
            # If example database found a product, skip validation and go to end
            if "Product found in Example Database" in last_message.content:
                print("✅ Example database found product - skipping validation")
                return "end"
        
        return "response_validation"

    # Node for handling all user requests
    def assistant(state: GraphState):
        messages = state["messages"]
        last_message = messages[-1]
        
        # Check if this is a fresh query that should ignore previous context
        # If there's only one message, it's a fresh query
        if len(messages) == 1:
            # Fresh query - use only current message
            system_message = get_upc_assistant_prompt()
            system_msg = SystemMessage(content=system_message)
            enhanced_messages = [system_msg, messages[0]]
            response = model.invoke(enhanced_messages)
            return {"messages": [response]}
        
        # Check if the current message explicitly references previous context
        current_message_content = messages[-1].content.lower()
        context_reference_indicators = [
            "before", "previous", "earlier", "last time", "that upc", "the product", 
            "what was", "what about", "tell me more about", "for the", "of the",
            "juice upc i asked about", "product i mentioned", "the one i asked about"
        ]
        
        is_context_reference = any(indicator in current_message_content for indicator in context_reference_indicators)
        
        if is_context_reference:
            # User is explicitly referencing previous context - use full conversation history
            system_message = get_upc_assistant_prompt()
            system_msg = SystemMessage(content=system_message)
            enhanced_messages = [system_msg] + messages
            response = model.invoke(enhanced_messages)
            return {"messages": [response]}
        
        # Check if the last message is a validation failure
        if hasattr(last_message, 'content') and "VALIDATION:FAIL" in last_message.content:
            # This is a regeneration request due to validation failure
            original_query = messages[0]
            validation_message = last_message
            
            # Find the previous response that failed validation
            previous_response = None
            tool_results = []
            
            # Collect all tool results and find the last assistant response before validation
            for msg in reversed(messages[:-1]):  # Exclude the validation message
                if hasattr(msg, 'content'):
                    if hasattr(msg, 'tool_calls'):
                        continue  # Skip assistant messages with tool calls
                    elif msg.type == "tool":
                        tool_results.insert(0, msg)  # Insert at beginning to maintain order
                    elif msg.type == "ai" and not "VALIDATION:" in msg.content:
                        previous_response = msg
                        break
            
            # Prepare context for regeneration prompt
            tool_results_text = chr(10).join([
                f"- {tool.content[:200]}..." if len(tool.content) > 200 else f"- {tool.content}" 
                for tool in tool_results[-6:]
            ])
            previous_response_text = previous_response.content[:500] + "..." if previous_response and len(previous_response.content) > 500 else previous_response.content if previous_response else "No previous response found"
            
            # Get regeneration prompt from prompts.py
            regeneration_prompt = get_context_aware_regeneration_prompt(
                validation_failure=validation_message.content,
                tool_results=tool_results_text,
                previous_response=previous_response_text
            )
            
            # Include the original query and all tool context
            system_msg = SystemMessage(content=regeneration_prompt)
            # Use the full conversation context for regeneration, not just the original query
            context_messages = [system_msg] + messages[:-1]  # Exclude the validation failure message
            
            response = model.invoke(context_messages)
            return {"messages": [response]}
        else:
            # Normal assistant operation for follow-up queries
            system_message = get_upc_assistant_prompt()
                    
            # Add the system message to the conversation
            system_msg = SystemMessage(content=system_message)
            enhanced_messages = [system_msg] + messages
            
            response = model.invoke(enhanced_messages)
            return {"messages": [response]}
  
    # Node
    tool_node = ToolNode(tool_belt)

    # Define a new graph for the agent
    builder = StateGraph(GraphState)

    # Define nodes
    builder.add_node("assistant", assistant)
    builder.add_node("tools", tool_node)
    builder.add_node("response_validation", response_validation_node)

    # Set the entrypoint as `assistant`
    builder.add_edge(START, "assistant")

    # Making a conditional edge from assistant
    # should_continue will determine which node is called next.
    builder.add_conditional_edges("assistant", should_continue, {"tools": "tools", "response_validation": "response_validation"})

    # Making a normal edge from `tools` to `assistant`.
    # The `assistant` node will be called after the `tool`.
    builder.add_edge("tools", "assistant")
    
    # Add validation workflow - routes back to assistant for regeneration or ends
    builder.add_conditional_edges(
        "response_validation",
        should_continue_after_validation,
        {
            "assistant": "assistant",
            "end": END
        }
    )

    # Compile and display the graph for a visual overview
    react_graph = builder.compile()
    if display_graph:
        display(Image(react_graph.get_graph(xray=True).draw_mermaid_png()))
    return react_graph

# Initialize the agent graph directly since API keys will be available in .env file
agent_graph = build_graph()