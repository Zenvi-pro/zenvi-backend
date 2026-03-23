"""
Chat session management.
Ported from zenvi-core — no Qt or app dependencies.
"""

import json
import uuid
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

from logger import log


class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    MEMORY = "memory"  # Ephemeral RAG context injected before each agent run


class ChatMessage:
    def __init__(self, role: MessageRole, content: str, context: Optional[Dict[str, Any]] = None):
        self.role = role
        self.content = content
        self.context = context or {}
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "content": self.content,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }


class ChatSession:
    def __init__(self, session_id: str = "", model: str = "default", system_prompt: str = ""):
        self.session_id = session_id or str(uuid.uuid4())
        self.model = model
        self.system_prompt = system_prompt
        self.messages: List[ChatMessage] = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.context_data: Dict[str, Any] = {}
        if system_prompt:
            self.add_message(MessageRole.SYSTEM, system_prompt)

    def add_message(self, role: MessageRole, content: str, context: Optional[Dict[str, Any]] = None) -> ChatMessage:
        msg = ChatMessage(role, content, context)
        self.messages.append(msg)
        self.updated_at = datetime.now()
        return msg

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self.messages]

    def clear_messages(self):
        system_msgs = [m for m in self.messages if m.role == MessageRole.SYSTEM]
        self.messages = system_msgs
        self.updated_at = datetime.now()

    def purge_memory_messages(self):
        """Remove ephemeral MEMORY-role messages after agent completes."""
        self.messages = [m for m in self.messages if m.role != MessageRole.MEMORY]

    def attach_context(self, key: str, value: Any):
        self.context_data[key] = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "model": self.model,
            "messages": self.get_conversation_history(),
            "context_data": self.context_data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class AIChat:
    """Main AI Chat manager — handles a single session."""

    def __init__(self, model: str = "default", system_prompt: str = ""):
        self.model = model
        self.system_prompt = system_prompt or (
            "You are an AI assistant for Zenvi. "
            "You help users with video editing, effects, transitions, and general editing tasks."
        )
        self.current_session: Optional[ChatSession] = None
        self._init_session()

    def _init_session(self):
        self.current_session = ChatSession(model=self.model, system_prompt=self.system_prompt)
        log.info("Chat session initialized: %s", self.current_session.session_id)

    def send_message(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        model_id: Optional[str] = None,
        tool_executor=None,
        memory_context: Optional[str] = None,
    ) -> str:
        """
        Send a message and get a response.
        tool_executor: optional callback for delegating tool calls to the frontend.
        memory_context: optional RAG context string retrieved from Pinecone.
        """
        if not self.current_session:
            self._init_session()

        self.current_session.add_message(MessageRole.USER, user_input, context)

        response = self._generate_response(
            user_input, model_id=model_id, tool_executor=tool_executor,
            memory_context=memory_context,
        )

        self.current_session.add_message(MessageRole.ASSISTANT, response)
        return response

    def _generate_response(
        self,
        user_input: str,
        model_id: Optional[str] = None,
        tool_executor=None,
        memory_context: Optional[str] = None,
    ) -> str:
        """Generate a response using the LangChain agent."""
        # Check if this is a media management command
        lower = (user_input or "").lower()
        clip_context_markers = ["@selected_clip", "[selected timeline clip context]", "selected clip"]
        refers_to_selected_clip = any(m in lower for m in clip_context_markers)

        media_keywords = ["analyze", "search", "find", "collection", "tag", "face", "statistics"]
        media_intent_markers = ["media", "library", "project files", "collection", "import", "file", "footage"]

        if (
            not refers_to_selected_clip
            and any(k in lower for k in media_keywords)
            and any(m in lower for m in media_intent_markers)
        ):
            try:
                from core.media.manager import get_ai_media_manager
                manager = get_ai_media_manager()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(manager.process_command(user_input))
                loop.close()
                if result.get("success"):
                    return result.get("message", "Command executed successfully")
                return result.get("message", "Command failed")
            except Exception as e:
                log.error("Media management command failed: %s", e)

        # Agent path
        try:
            from core.chat.agent_runner import run_agent
            from core.llm import get_default_model_id
        except ImportError as e:
            log.warning("Agent runner not available: %s", e)
            return "AI agent is not available. Check backend dependencies."

        resolved_model_id = model_id or get_default_model_id()
        messages = self.current_session.get_conversation_history() if self.current_session else []
        if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != user_input:
            messages = list(messages) + [{"role": "user", "content": user_input}]

        # Inject Pinecone RAG context just before the final user message
        if memory_context:
            insert_pos = len(messages) - 1  # before last (user) message
            messages = (
                list(messages[:insert_pos])
                + [{"role": "memory", "content": memory_context}]
                + list(messages[insert_pos:])
            )

        try:
            result = run_agent(resolved_model_id, messages, tool_executor=tool_executor)
        except Exception as e:
            log.error("run_agent raised: %s", e, exc_info=True)
            result = f"Error: {e}"

        return result or "Error: No response from agent."

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        if not self.current_session:
            return []
        return self.current_session.get_conversation_history()

    def clear_session(self):
        self._init_session()

    def get_session_info(self) -> Dict[str, Any]:
        if not self.current_session:
            return {}
        return {
            "session_id": self.current_session.session_id,
            "model": self.current_session.model,
            "message_count": len(self.current_session.messages),
            "created_at": self.current_session.created_at.isoformat(),
            "updated_at": self.current_session.updated_at.isoformat(),
        }
