"""
Per-session vector memory backed by Pinecone.

Each chat session gets its own Pinecone namespace (multi-tenancy).
Conversation exchanges are embedded and stored so the agent can RAG
relevant past context on every new message.

Lifecycle:
  - upsert_exchange()  — called after each assistant reply
  - query_relevant()   — called before each agent run to inject context
  - delete_session()   — called on session clear/delete (frees namespace)
"""

import uuid
from typing import List, Dict, Any, Optional

from logger import log

# Pinecone index shared across all sessions
_INDEX_NAME = "zenvi-sessions"
_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIM = 1536
_SIMILARITY_THRESHOLD = 0.72


class PineconeMemory:
    """Thin wrapper around Pinecone for per-session RAG memory."""

    def __init__(self, pinecone_api_key: str, openai_api_key: str):
        from pinecone import Pinecone, ServerlessSpec

        self._pc = Pinecone(api_key=pinecone_api_key)
        self._openai_api_key = openai_api_key
        self._index = self._get_or_create_index()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert_exchange(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        """Embed and store a user↔assistant exchange under the session namespace."""
        try:
            text = f"User: {user_msg}\nAssistant: {assistant_msg}"
            vector = self._embed(text)
            self._index.upsert(
                vectors=[{
                    "id": str(uuid.uuid4()),
                    "values": vector,
                    "metadata": {
                        "user_msg": user_msg[:1500],
                        "assistant_msg": assistant_msg[:1500],
                        "session_id": session_id,
                    },
                }],
                namespace=session_id,
            )
        except Exception as e:
            log.warning("Pinecone upsert failed (non-fatal): %s", e)

    def query_relevant(self, session_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Return past exchanges semantically relevant to *query* for this session."""
        try:
            vector = self._embed(query)
            result = self._index.query(
                vector=vector,
                top_k=top_k,
                namespace=session_id,
                include_metadata=True,
            )
            return [
                m.metadata
                for m in result.matches
                if m.score >= _SIMILARITY_THRESHOLD
            ]
        except Exception as e:
            log.warning("Pinecone query failed (non-fatal): %s", e)
            return []

    def delete_session(self, session_id: str) -> None:
        """Delete all vectors in the session namespace (frees tenant storage)."""
        try:
            self._index.delete(delete_all=True, namespace=session_id)
            log.info("Pinecone namespace deleted: %s", session_id)
        except Exception as e:
            # NotFoundException (404) means the namespace never had any vectors —
            # nothing to delete, this is not an error.
            err_str = str(e).lower()
            if "not found" in err_str or "404" in err_str or "namespace not found" in err_str:
                log.debug("Pinecone namespace '%s' has no vectors (nothing to delete)", session_id)
            else:
                log.warning("Pinecone namespace delete failed: %s", e)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_index(self):
        from pinecone import ServerlessSpec

        existing = {idx.name for idx in self._pc.list_indexes()}
        if _INDEX_NAME not in existing:
            log.info("Creating Pinecone index '%s'", _INDEX_NAME)
            self._pc.create_index(
                name=_INDEX_NAME,
                dimension=_EMBEDDING_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            # Wait until the index is ready
            import time
            for _ in range(30):
                info = self._pc.describe_index(_INDEX_NAME)
                if getattr(info.status, "ready", False):
                    break
                time.sleep(2)

        return self._pc.Index(_INDEX_NAME)

    def _embed(self, text: str) -> List[float]:
        from openai import OpenAI
        client = OpenAI(api_key=self._openai_api_key)
        resp = client.embeddings.create(model=_EMBEDDING_MODEL, input=text)
        return resp.data[0].embedding


# ---------------------------------------------------------------------------
# Module-level singleton — lazily initialised
# ---------------------------------------------------------------------------

_memory: Optional[PineconeMemory] = None


def get_memory() -> Optional[PineconeMemory]:
    """
    Return the shared PineconeMemory instance, or None if not configured.
    Safe to call even when PINECONE_API_KEY is absent — callers should
    check for None before using.
    """
    global _memory
    if _memory is not None:
        return _memory

    try:
        from config import get_settings
        settings = get_settings()
        pinecone_key = settings.pinecone_api_key
        openai_key = settings.openai_api_key

        if not pinecone_key:
            log.debug("PINECONE_API_KEY not set — session memory disabled")
            return None
        if not openai_key:
            log.warning("OPENAI_API_KEY not set — Pinecone embeddings unavailable")
            return None

        _memory = PineconeMemory(pinecone_key, openai_key)
        log.info("Pinecone session memory initialised (index: %s)", _INDEX_NAME)
    except Exception as e:
        log.warning("Failed to initialise Pinecone memory: %s", e)
        return None

    return _memory


def format_memory_context(exchanges: List[Dict[str, Any]]) -> str:
    """Format retrieved exchanges into a readable context block for the agent."""
    if not exchanges:
        return ""
    lines = ["[Relevant context from earlier in this session:]"]
    for ex in exchanges:
        lines.append(f"• User said: {ex.get('user_msg', '')}")
        lines.append(f"  Agent did: {ex.get('assistant_msg', '')}")
    return "\n".join(lines)
