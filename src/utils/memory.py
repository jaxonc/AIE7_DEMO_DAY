"""
S.A.V.E. Memory Management System

This module provides session-based memory management for the S.A.V.E. system,
enabling workflow continuity while maintaining cost efficiency.
"""

import os
import time
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
import tiktoken


@dataclass
class ProductContext:
    """Tracks current product context for workflow continuity"""
    upc: Optional[str] = None
    product_name: Optional[str] = None
    validation_status: Optional[str] = None
    correction_history: List[str] = None
    
    def __post_init__(self):
        if self.correction_history is None:
            self.correction_history = []
    
    def update_context(self, upc: str, name: str, status: str):
        """Update current product context"""
        self.upc = upc
        self.product_name = name
        self.validation_status = status
    
    def add_correction(self, correction: str):
        """Add a correction to the history"""
        self.correction_history.append(correction)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SAVESession:
    """Manages session-scoped memory for S.A.V.E. conversations"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: List[BaseMessage] = []
        self.product_context = ProductContext()
        self.validation_history: List[Dict[str, Any]] = []
        self.created_at = time.time()
        self.last_activity = time.time()
        
        # Memory limits
        self.max_messages = 15
        self.max_tokens = 6000
        self.session_timeout = 1800  # 30 minutes
    
    def add_message(self, message: BaseMessage):
        """Add a message and manage memory limits"""
        self.messages.append(message)
        self.last_activity = time.time()
        self._manage_memory()
    
    def add_product_validation(self, upc: str, name: str, status: str, details: Dict[str, Any]):
        """Track product validation history"""
        validation_record = {
            'upc': upc,
            'name': name,
            'status': status,
            'details': details,
            'timestamp': time.time()
        }
        self.validation_history.append(validation_record)
        
        # Keep only last 10 validations
        if len(self.validation_history) > 10:
            self.validation_history = self.validation_history[-10:]
    
    def _manage_memory(self):
        """Manage memory limits and optimize conversation history"""
        # Check if session has timed out
        if self._is_session_expired():
            self._clear_session()
            return
        
        # Remove oldest messages if limit exceeded
        if len(self.messages) > self.max_messages:
            # Keep system prompt + last 10 messages
            system_messages = [msg for msg in self.messages if isinstance(msg, SystemMessage)]
            recent_messages = self.messages[-10:]
            self.messages = system_messages + recent_messages
        
        # Optimize for token usage
        self._optimize_tokens()
    
    def _is_session_expired(self) -> bool:
        """Check if session has timed out"""
        return (time.time() - self.last_activity) > self.session_timeout
    
    def _clear_session(self):
        """Clear session data"""
        self.messages = []
        self.product_context = ProductContext()
        self.validation_history = []
    
    def _optimize_tokens(self):
        """Optimize message history for token usage"""
        estimated_tokens = self._estimate_tokens()
        
        if estimated_tokens > self.max_tokens:
            # Keep system messages
            system_messages = [msg for msg in self.messages if isinstance(msg, SystemMessage)]
            
            # Keep most recent messages, but limit to stay under token budget
            recent_messages = self.messages[-8:]  # Reduce to 8 recent messages
            
            # If still over limit, create summary of older messages
            if len(self.messages) > 10:
                summary = self._create_conversation_summary()
                summary_message = SystemMessage(content=summary)
                self.messages = system_messages + [summary_message] + recent_messages[-6:]
            else:
                self.messages = system_messages + recent_messages
    
    def _estimate_tokens(self) -> int:
        """Estimate token count for current messages"""
        try:
            # Use cl100k_base encoding which is compatible with Claude models and GPT-4
            # This is more accurate than using a specific model name for token counting
            encoding = tiktoken.get_encoding("cl100k_base")
            total_tokens = 0
            
            for message in self.messages:
                if hasattr(message, 'content') and message.content:
                    total_tokens += len(encoding.encode(message.content))
            
            return total_tokens
        except Exception:
            # Fallback estimation: ~4 characters per token
            total_chars = sum(len(str(msg.content)) for msg in self.messages if hasattr(msg, 'content'))
            return total_chars // 4
    
    def _create_conversation_summary(self) -> str:
        """Create a summary of older conversation messages"""
        product_count = len(self.validation_history)
        
        if product_count > 0:
            recent_products = self.validation_history[-3:]
            product_names = [p['name'] for p in recent_products if p.get('name')]
            
            if product_names:
                return f"Previous conversation: Validated {product_count} products including {', '.join(product_names)}. User requested UPC validation, nutritional information, and ingredient details."
        
        return f"Previous conversation: User has validated {product_count} products with UPC codes and requested nutritional/ingredient information."
    
    def get_optimized_messages(self) -> List[BaseMessage]:
        """Get optimized message history for the agent"""
        return self.messages.copy()
    
    def get_product_context(self) -> ProductContext:
        """Get current product context"""
        return self.product_context
    
    def update_product_context(self, upc: str, name: str, status: str):
        """Update current product context"""
        self.product_context.update_context(upc, name, status)
    
    def is_active(self) -> bool:
        """Check if session is still active"""
        return not self._is_session_expired()


class SAVEMemoryManager:
    """Manages a single S.A.V.E. session"""
    
    def __init__(self):
        self.session: Optional[SAVESession] = None
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
    
    def get_session(self, session_id: str = "default") -> SAVESession:
        """Get or create the single session"""
        if self.session is None:
            self.session = SAVESession(session_id)
        return self.session
    
    def add_message(self, session_id: str = "default", message: BaseMessage = None):
        """Add a message to the session"""
        session = self.get_session(session_id)
        if message:
            session.add_message(message)
    
    def get_conversation_context(self, session_id: str = "default", user_message: BaseMessage = None) -> List[BaseMessage]:
        """Get optimized conversation context for the agent"""
        session = self.get_session(session_id)
        
        # Return optimized message history WITHOUT adding the current message yet
        # The current message will be added after successful processing
        return session.get_optimized_messages()
    
    def reset_session(self):
        """Reset the single session, clearing all memory"""
        if self.session:
            self.session._clear_session()
        else:
            self.session = SAVESession("default")
    
    def cleanup_expired_sessions(self):
        """Check if the single session has expired and reset if needed"""
        current_time = time.time()
        
        # Only cleanup every 5 minutes to avoid performance impact
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        if self.session and not self.session.is_active():
            print("🧹 Session expired, resetting...")
            self.reset_session()
        
        self.last_cleanup = current_time
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get memory manager statistics"""
        if self.session:
            return {
                "active_sessions": 1 if self.session.is_active() else 0,
                "total_sessions": 1,
                "expired_sessions": 0 if self.session.is_active() else 1,
                "session_id": self.session.session_id,
                "message_count": len(self.session.messages),
                "last_activity": self.session.last_activity
            }
        else:
            return {
                "active_sessions": 0,
                "total_sessions": 0,
                "expired_sessions": 0,
                "session_id": None,
                "message_count": 0,
                "last_activity": None
            }


# Global memory manager instance
memory_manager = SAVEMemoryManager()


def get_memory_manager() -> SAVEMemoryManager:
    """Get the global memory manager instance"""
    return memory_manager
