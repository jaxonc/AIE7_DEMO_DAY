import os
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from typing import Union

def get_model(model_name: str = None) -> Union[ChatAnthropic, ChatOpenAI]:
  # Use environment variable as default if no model_name provided
  if model_name is None:
    model_name = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
  
  try:
    if model_name.startswith('claude'):
      # Check for Anthropic API key
      if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
      model = ChatAnthropic(model=model_name)
    elif model_name.startswith('gpt'):
      # Check for OpenAI API key
      if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not found in environment variables")
      model = ChatOpenAI(model=model_name)
    else:
      raise ValueError(f"Model {model_name} not supported")
    
    print(f"✅ Successfully initialized model: {model_name}")
    return model
  except Exception as e:
    print(f"❌ Failed to initialize model {model_name}: {e}")
    raise