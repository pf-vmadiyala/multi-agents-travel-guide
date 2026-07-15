from langchain_core.language_models import BaseChatModel
import os
from typing import Any, List
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

def get_llm() -> BaseChatModel:
    """
    Factory function that loads and configures the LLM provider 
    based on environment variables.
    """
    provider = os.getenv("LLM_PROVIDER", "local").lower()
    model_name = os.getenv("LLM_MODEL_NAME", "qwen3:4b")
    
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        # LangChain handles ANTHROPIC_API_KEY from environment automatically
        return ChatAnthropic(
            model_name=model_name,
            temperature=0.2,
        )
        
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        # LangChain handles OPENAI_API_KEY from environment automatically
        return ChatOpenAI(
            model_name=model_name,
            temperature=0.2,
        )
        
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        # LangChain handles GOOGLE_API_KEY from environment automatically
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.2,
        )
    elif provider == "xai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("XAI_API_KEY")
        return ChatOpenAI(
            model_name=model_name,
            base_url="https://api.x.ai/v1",
            api_key=api_key,
            temperature=0.2,
        )
        
    elif provider in ("local", "ollama"):
        from langchain_openai import ChatOpenAI
        base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
        api_key = os.getenv("LLM_API_KEY", "ollama")
        
        # Local LLMs like Qwen (Ollama/vLLM) use the OpenAI-compatible client
        return ChatOpenAI(
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            temperature=0.2,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


