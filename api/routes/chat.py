"""
Chat endpoints — REST for simple request/response, WebSocket for streaming + tool delegation.
"""

import json
import asyncio
import threading
import uuid
from typing import Dict, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.schemas import (
    ChatRequest, ChatResponse, ChatHistoryResponse, ChatSessionInfo, ChatMessageSchema, StatusResponse,
)
from logger import log

router = APIRouter(prefix="/chat", tags=["chat"])

# In-memory session store (in production, use Redis or DB)
_sessions: Dict[str, "core.chat.functionality.AIChat"] = {}


def _get_or_create_session(session_id: Optional[str] = None, model_id: Optional[str] = None):
    from core.chat.functionality import AIChat
    if session_id and session_id in _sessions:
        return _sessions[session_id], session_id
    chat = AIChat(model=model_id or "default")
    sid = chat.current_session.session_id
    _sessions[sid] = chat
    return chat, sid


@router.post("", response_model=ChatResponse)
def send_message(req: ChatRequest):
    """Send a chat message and get a response (synchronous, no tool delegation)."""
    chat, sid = _get_or_create_session(req.session_id, req.model_id)
    response = chat.send_message(req.message, context=req.context, model_id=req.model_id)
    return ChatResponse(response=response, session_id=sid, model_id=req.model_id or "default")


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
def get_history(session_id: str):
    """Get conversation history for a session."""
    if session_id not in _sessions:
        return ChatHistoryResponse(
            messages=[],
            session_info=ChatSessionInfo(session_id=session_id),
        )
    chat = _sessions[session_id]
    history = chat.get_conversation_history()
    info = chat.get_session_info()
    return ChatHistoryResponse(
        messages=[ChatMessageSchema(**m) for m in history],
        session_info=ChatSessionInfo(**info),
    )


@router.post("/clear/{session_id}", response_model=StatusResponse)
def clear_session(session_id: str):
    """Clear a chat session."""
    if session_id in _sessions:
        _sessions[session_id].clear_session()
        return StatusResponse(success=True, message="Session cleared")
    return StatusResponse(success=False, message="Session not found")


@router.delete("/session/{session_id}", response_model=StatusResponse)
def delete_session(session_id: str):
    """Delete a chat session."""
    if session_id in _sessions:
        del _sessions[session_id]
        return StatusResponse(success=True, message="Session deleted")
    return StatusResponse(success=False, message="Session not found")


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for streaming chat with bidirectional tool execution.

    Protocol:
    1. Client sends: {"type": "user_message", "data": {"message": "...", "model_id": "...", "session_id": "..."}}
    2. Server may send: {"type": "tool_call", "data": {"tool_name": "...", "tool_args": {...}, "call_id": "..."}}
    3. Client responds: {"type": "tool_result", "data": {"call_id": "...", "result": "..."}}
    4. Server sends: {"type": "assistant_response", "data": {"response": "...", "session_id": "..."}}
    5. Server sends: {"type": "done", "data": {}}
    """
    await websocket.accept()
    log.info("WebSocket chat connection established")

    # Shared state between the agent thread and the WebSocket event loop
    pending_tool_calls: Dict[str, asyncio.Future] = {}
    loop = asyncio.get_event_loop()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "data": {"message": "Invalid JSON"}})
                continue

            msg_type = msg.get("type", "")
            data = msg.get("data", {})

            if msg_type == "user_message":
                message = data.get("message", "")
                model_id = data.get("model_id")
                session_id = data.get("session_id")

                chat, sid = _get_or_create_session(session_id, model_id)

                def make_tool_executor():
                    """Create a synchronous tool executor that bridges to the async WebSocket."""
                    def executor(req):
                        from core.chat.agent_runner import ToolExecutionResult

                        # Create a future on the main event loop
                        future = loop.create_future()
                        pending_tool_calls[req.call_id] = future

                        # Send tool_call to frontend
                        asyncio.run_coroutine_threadsafe(
                            websocket.send_json({
                                "type": "tool_call",
                                "data": req.to_dict(),
                            }),
                            loop,
                        ).result(timeout=5)

                        # Wait for the frontend to send the result back
                        try:
                            result = asyncio.run_coroutine_threadsafe(
                                asyncio.wait_for(future, timeout=120),
                                loop,
                            ).result(timeout=125)
                            return result
                        except Exception as e:
                            return ToolExecutionResult(req.call_id, f"Error: Tool execution timed out: {e}")
                        finally:
                            pending_tool_calls.pop(req.call_id, None)

                    return executor

                tool_executor = make_tool_executor()

                # Run agent in background thread so we can still receive messages
                agent_done = asyncio.Event()
                agent_result = {"response": "", "error": ""}

                def run_in_thread():
                    try:
                        from core.chat.agent_runner import run_agent
                        response = run_agent(
                            model_id or "default",
                            chat.current_session.get_conversation_history() + [{"role": "user", "content": message}],
                            tool_executor=tool_executor,
                        )
                        chat.current_session.add_message(
                            chat.current_session.messages[0].role.__class__("user"), message
                        ) if False else None  # noqa — history is managed by AIChat
                        agent_result["response"] = response
                    except Exception as e:
                        log.error("WebSocket agent error: %s", e, exc_info=True)
                        agent_result["error"] = str(e)
                    finally:
                        loop.call_soon_threadsafe(agent_done.set)

                thread = threading.Thread(target=run_in_thread, daemon=True)
                thread.start()

                # Process incoming messages (tool results) while agent runs
                while not agent_done.is_set():
                    try:
                        # Wait for either a message or the agent to finish
                        done, _ = await asyncio.wait(
                            [
                                asyncio.ensure_future(asyncio.to_thread(lambda: agent_done.wait(0.1))),
                                asyncio.ensure_future(
                                    asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                                ),
                            ],
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        for task in done:
                            try:
                                result = task.result()
                                if isinstance(result, str):
                                    # Got a message from the client
                                    inner_msg = json.loads(result)
                                    if inner_msg.get("type") == "tool_result":
                                        inner_data = inner_msg.get("data", {})
                                        call_id = inner_data.get("call_id", "")
                                        if call_id in pending_tool_calls:
                                            from core.chat.agent_runner import ToolExecutionResult
                                            ter = ToolExecutionResult(
                                                call_id,
                                                inner_data.get("result", ""),
                                                inner_data.get("error"),
                                            )
                                            pending_tool_calls[call_id].set_result(ter)
                            except (asyncio.TimeoutError, asyncio.CancelledError):
                                pass
                            except Exception:
                                pass
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass
                    except Exception:
                        break

                thread.join(timeout=5)

                if agent_result["error"]:
                    await websocket.send_json({
                        "type": "error",
                        "data": {"message": agent_result["error"]},
                    })
                else:
                    await websocket.send_json({
                        "type": "assistant_response",
                        "data": {"response": agent_result["response"], "session_id": sid},
                    })
                await websocket.send_json({"type": "done", "data": {}})

            elif msg_type == "tool_result":
                # Tool result arriving outside of the agent loop (late/orphaned)
                call_id = data.get("call_id", "")
                if call_id in pending_tool_calls and not pending_tool_calls[call_id].done():
                    from core.chat.agent_runner import ToolExecutionResult
                    pending_tool_calls[call_id].set_result(
                        ToolExecutionResult(call_id, data.get("result", ""), data.get("error"))
                    )

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong", "data": {}})

    except WebSocketDisconnect:
        log.info("WebSocket chat disconnected")
    except Exception as e:
        log.error("WebSocket error: %s", e, exc_info=True)
