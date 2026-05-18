import json
import uuid
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.service.multi_agent import run_multi_agent, run_multi_agent_stream
from src.core.tool import TOOLS
from src.core.memory import load_messages, load_summary, save_summary
from src.service.context_persistence import load_durable_session_summary

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


class AgentRunRequest(BaseModel):
    task: str
    session_id: str = ""
    space_id: str = "0"
    user_id: int = 0
    max_steps: int = 10


@router.post("/run")
def agent_run(req: AgentRunRequest):
    session_id = req.session_id or str(uuid.uuid4())
    result = run_multi_agent(req.task, session_id, req.space_id, req.max_steps, req.user_id)
    return {"answer": result["answer"], "steps": result["steps"], "session_id": session_id}


@router.post("/run/stream")
async def agent_run_stream(req: AgentRunRequest):
    session_id = req.session_id or str(uuid.uuid4())
    logger.info(
        "Multi-agent stream request: task=%s, space_id=%s, user_id=%s, session=%s",
        req.task[:50], req.space_id, req.user_id, session_id
    )

    async def generate():
        async for chunk in run_multi_agent_stream(req.task, session_id, req.space_id, req.max_steps, req.user_id):
            yield chunk.encode("utf-8") if isinstance(chunk, str) else chunk
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/tools")
def list_tools():
    return [{"name": t.name, "description": t.description} for t in TOOLS]


@router.get("/messages/{session_id}")
def get_messages(session_id: str, user_id: int = 0):
    raw = load_messages(session_id)
    messages = []
    for m in raw:
        role = m.get("role", "")
        if role not in ("user", "assistant"):
            continue
        content = m.get("content", "")
        if not content or not content.strip():
            continue
        messages.append({"role": role, "content": content})
    if not messages:
        summary = load_summary(session_id)
        if not summary:
            summary = load_durable_session_summary(session_id, user_id)
            if summary:
                save_summary(session_id, summary)
        if summary:
            messages.append({
                "role": "assistant",
                "content": f"已从历史摘要恢复会话上下文：{summary}",
            })
    return {"messages": messages}
