"""
S.A.V.E. Memory Management System

This module provides session-based memory management for the S.A.V.E. system,
enabling workflow continuity while maintaining cost efficiency.
"""

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
            encoding = tiktoken.encoding_for_model("gpt-4")
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
    """Manages multiple S.A.V.E. sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, SAVESession] = {}
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
    
    def get_session(self, session_id: str) -> SAVESession:
        """Get or create a session"""
        if session_id not in self.sessions:
            self.sessions[session_id] = SAVESession(session_id)
        return self.sessions[session_id]
    
    def add_message(self, session_id: str, message: BaseMessage):
        """Add a message to a session"""
        session = self.get_session(session_id)
        session.add_message(message)
    
    def get_conversation_context(self, session_id: str, user_message: BaseMessage) -> List[BaseMessage]:
        """Get optimized conversation context for the agent"""
        session = self.get_session(session_id)
        
        # Add current message
        session.add_message(user_message)
        
        # Return optimized message history
        return session.get_optimized_messages()
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions to free memory"""
        current_time = time.time()
        
        # Only cleanup every 5 minutes to avoid performance impact
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        expired_sessions = [
            session_id for session_id, session in self.sessions.items()
            if not session.is_active()
        ]
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
        
        self.last_cleanup = current_time
        
        if expired_sessions:
            print(f"🧹 Cleaned up {len(expired_sessions)} expired sessions")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get memory manager statistics"""
        active_sessions = sum(1 for session in self.sessions.values() if session.is_active())
        total_sessions = len(self.sessions)
        
        return {
            "active_sessions": active_sessions,
            "total_sessions": total_sessions,
            "expired_sessions": total_sessions - active_sessions
        }


# Global memory manager instance
memory_manager = SAVEMemoryManager()


def get_memory_manager() -> SAVEMemoryManager:
    """Get the global memory manager instance"""
    return memory_manager
