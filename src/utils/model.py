import os
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from typing import Union

def get_model(model_name: str = None) -> Union[ChatAnthropic, ChatOpenAI]:
  # Use environment variable as default if no model_name provided
  if model_name is None:
    model_name = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
  
  if model_name.startswith('claude'):
    model = ChatAnthropic(model=model_name)
  elif model_name.startswith('gpt'):
    model = ChatOpenAI(model=model_name)
  else:
    raise ValueError(f"Model {model_name} not supported")
  return model