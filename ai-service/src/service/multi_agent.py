import asyncio
import json
import logging
import re
from typing import Literal, Optional

from langgraph.graph import StateGraph, END
from src.service.llm import get_llm_client, _normalize_messages
from src.service.prompt import PLAN_PROMPT
from src.core.multi_agent_state import MultiAgentState, SubTask
from src.core.picture_id_utils import extract_picture_ids_from_text, resolve_ordinal_references
from src.core.tag_utils import extract_add_tag, extract_remove_tag
from src.service.expert_searcher import build_searcher_agent
from src.service.expert_editor import build_editor_agent
from src.service.expert_analyst import build_analyst_agent
from src.config import settings

logger = logging.getLogger(__name__)

MAX_SUPERVISOR_ROUNDS = 10
MAX_EXPERT_RESULT_CHARS = 12000
ANSWER_STREAM_CHUNK_SIZE = 36
ANSWER_STREAM_DELAY_SECONDS = 0.01

# 单例子图
searcher_app = build_searcher_agent()
editor_app = build_editor_agent()
analyst_app = build_analyst_agent()


# --- Plan 辅助函数 ---

def _extract_json_array(content: str) -> str:
    """从 LLM 输出中提取 JSON 数组，兼容 ```json fenced block。"""
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text).strip()
    if text.startswith("[") and text.endswith("]"):
        return text

    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text


def _normalize_plan_description(description: str, agent: str, task_text: str) -> str:
    remove_tag = extract_remove_tag(task_text)
    add_tag = extract_add_tag(task_text)
    if remove_tag and agent == "searcher":
        return (
            f'按业务标签搜索当前空间中包含 "{remove_tag}" 标签的图片，'
            f'使用 search_pictures_by_tag(tag="{remove_tag}") 返回所有 picture_ids。'
            f"原始子任务：{description}"
        )
    if agent != "editor":
        return description

    if remove_tag and "remove_tags" not in description:
        return f'{description}；使用 edit_picture(remove_tags="{remove_tag}")'
    if add_tag and "tags" not in description and "remove_tags" not in description:
        return f'{description}；使用 edit_picture(tags="{add_tag}")'
    return description



def _last_search_results(tool_context: dict) -> list[dict]:
    results = (tool_context or {}).get("last_search_results", [])
    return results if isinstance(results, list) else []


def _all_search_results(tool_context: dict) -> list[dict]:
    from src.core.tool_context import get_all_search_results
    return get_all_search_results(tool_context or {})





def _format_tool_context_hint(task_text: str, tool_context: dict) -> str:
    latest = _last_search_results(tool_context)
    all_results = _all_search_results(tool_context)
    if not all_results:
        return ""

    lines = []

    # 最新一轮结果（用于 "第N张"、"这些图片" 等指代）
    if latest:
        lines.append("最近一次搜索结果：")
        for item in latest[:20]:
            rank = item.get("rank", "")
            picture_id = item.get("id", "")
            name = item.get("name", "")
            lines.append(f"- rank={rank}, id={picture_id}, name={name}")

    # 更早的搜索结果（用于跨轮次的命名指代，如 "红色赛车"）
    older = [r for r in all_results if r not in latest]
    if older:
        lines.append("更早的搜索结果：")
        for item in older[:20]:
            picture_id = item.get("id", "")
            name = item.get("name", "")
            lines.append(f"- id={picture_id}, name={name}")

    # 用最新结果解析序号指代
    picture_ids = resolve_ordinal_references(task_text, latest)
    if picture_ids:
        lines.append(f"根据当前用户指代解析出的 picture_ids：{','.join(picture_ids)}")
    return "\n".join(lines)


def _items_to_plan(plan_data: list, task_text: str) -> list[SubTask]:
    valid_agents = {"searcher", "editor", "analyst"}
    plan = []
    for i, item in enumerate(plan_data):
        if not isinstance(item, dict):
            continue
        agent = item.get("agent", "searcher")
        if agent not in valid_agents:
            agent = "searcher"
        description = _normalize_plan_description(item.get("description", ""), agent, task_text)
        plan.append({
            "id": str(item.get("id", i + 1)),
            "description": description,
            "agent": agent,
            "status": "pending",
            "result": "",
        })
    return plan


def _fallback_plan(task_text: str) -> list[SubTask]:
    remove_tag = extract_remove_tag(task_text)
    if remove_tag:
        return _items_to_plan([
            {
                "id": "1",
                "description": task_text,
                "agent": "searcher",
            },
            {
                "id": "2",
                "description": f'使用上游搜索结果中的 picture_ids，删除这些图片的 {remove_tag} 标签',
                "agent": "editor",
            },
        ], task_text)

    return [{
        "id": "1",
        "description": task_text,
        "agent": "searcher",
        "status": "pending",
        "result": "",
    }]


def _generate_plan(state: MultiAgentState) -> list[SubTask]:
    """调用 LLM 生成任务 plan。单步输出 1 元素，多步输出 N 元素。"""
    from src.core.memory import load_messages

    client = get_llm_client()
    task_text = state.get("current_task", "")
    session_id = state.get("session_id", "")
    prompt = PLAN_PROMPT.replace("{user_message}", task_text)
    context_hint = _format_tool_context_hint(task_text, state.get("tool_context", {}))
    if context_hint:
        prompt += (
            "\n\n"
            f"{context_hint}\n"
            "如果当前用户需求包含指代，请优先使用上述解析出的 picture_ids。"
        )

    # 加载最近对话历史，让规划 LLM 理解跨轮次指代
    history_messages = []
    if session_id:
        history = load_messages(session_id)
        for m in history[-12:]:
            if not isinstance(m, dict):
                continue
            role = m.get("role", "")
            content = str(m.get("content", "")).strip()
            if role in ("user", "assistant") and content:
                history_messages.append({"role": role, "content": content})

    msgs = [{"role": "system", "content": prompt}]
    msgs.extend(history_messages)
    msgs.append({"role": "user", "content": task_text})

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=_normalize_messages(msgs),
    )
    content = response.choices[0].message.content or "[]"

    try:
        plan_data = json.loads(_extract_json_array(content))
        if not isinstance(plan_data, list):
            raise ValueError("plan JSON must be an array")
        plan = _items_to_plan(plan_data, task_text)
        return plan or _fallback_plan(task_text)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse plan JSON: {content}")
        return _fallback_plan(task_text)
    except ValueError as e:
        logger.warning(f"Invalid plan JSON: {e}; content={content}")
        return _fallback_plan(task_text)


def _update_plan_after_expert(plan: list[SubTask], subtask_id: str,
                               status: str, result: str) -> list[SubTask]:
    """更新 plan 中指定子任务的状态和结果。"""
    updated = []
    for task in plan:
        if task["id"] == subtask_id:
            updated.append({**task, "status": status, "result": _clip_expert_result(result)})
        else:
            updated.append(task)
    return updated


def _clip_expert_result(result: str) -> str:
    """保留专家结果，必要时只在换行边界截断，避免切断 markdown 图片链接。"""
    if len(result) <= MAX_EXPERT_RESULT_CHARS:
        return result
    clipped = result[:MAX_EXPERT_RESULT_CHARS]
    newline_index = clipped.rfind("\n")
    if newline_index > MAX_EXPERT_RESULT_CHARS * 0.6:
        clipped = clipped[:newline_index]
    return clipped.rstrip() + "\n...（专家结果过长，已省略后续内容）"




def _split_answer_for_stream(answer: str) -> list[str]:
    """Split final answer into display chunks without cutting markdown links."""
    chunks = []
    for line in str(answer or "").splitlines(keepends=True):
        if not line:
            continue
        stripped = line.strip()
        if "](" in stripped or len(line) <= ANSWER_STREAM_CHUNK_SIZE:
            chunks.append(line)
            continue
        for i in range(0, len(line), ANSWER_STREAM_CHUNK_SIZE):
            chunks.append(line[i:i + ANSWER_STREAM_CHUNK_SIZE])
    return chunks


async def _yield_answer_stream(answer: str):
    for chunk in _split_answer_for_stream(answer):
        if not chunk:
            continue
        yield f"data: {json.dumps({'type': 'reasoning', 'content': chunk}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(ANSWER_STREAM_DELAY_SECONDS)


def _build_expert_task_description(plan: list[SubTask], current_id: str,
                                   tool_context: Optional[dict] = None,
                                   original_task: str = "") -> str:
    """把当前任务和已完成的上游结果一起交给专家，保证搜后编辑能拿到 ID。"""
    current_task = ""
    prior_results = []
    for task in plan:
        if task["id"] == current_id:
            current_task = task.get("description", "")
            break
        if task.get("status") == "done" and task.get("result"):
            prior_results.append(task)

    if not prior_results:
        context_hint = _format_tool_context_hint(f"{original_task}\n{current_task}", tool_context or {})
        if context_hint:
            return "\n".join([current_task, "", context_hint])
        return current_task

    lines = [f"当前子任务：{current_task}", "", "上游已完成任务结果："]
    combined_results = []
    for task in prior_results:
        result = task.get("result", "")
        combined_results.append(result)
        lines.append(f"[{task.get('agent')}] {task.get('description')}：")
        lines.append(result)

    picture_ids = extract_picture_ids_from_text("\n".join(combined_results))
    if picture_ids:
        lines.extend([
            "",
            f"从上游结果中提取到的 picture_ids：{','.join(picture_ids)}",
            "如果当前任务要处理“上述图片/这些图片/全部结果”，请直接使用这些 picture_ids。",
        ])

    context_hint = _format_tool_context_hint(f"{original_task}\n{current_task}", tool_context or {})
    if context_hint:
        lines.extend(["", context_hint])

    return "\n".join(lines)


# --- Supervisor 节点 ---

def supervisor_node(state: MultiAgentState) -> dict:
    plan = state.get("plan", [])
    current_id = state.get("current_subtask", "")

    # 第一次进入：LLM 规划
    if not plan:
        plan = _generate_plan(state)
        first = plan[0] if plan else None
        return {
            "plan": plan,
            "current_subtask": first["id"] if first else "",
            "next_agent": first["agent"] if first else "summarize",
            "supervisor_round": 1,
        }

    # 专家返回后：更新 plan
    round_count = state.get("supervisor_round", 0) + 1
    if round_count > MAX_SUPERVISOR_ROUNDS:
        return {
            "plan": plan,
            "next_agent": "summarize",
            "supervisor_round": round_count,
        }

    if current_id:
        # 从专家返回的 messages 中取最后一条 assistant 消息作为结果
        expert_result = ""
        for m in reversed(state["messages"]):
            if isinstance(m, dict) and m.get("role") == "assistant" and m.get("content"):
                expert_result = m["content"]
                break
        plan = _update_plan_after_expert(plan, current_id, "done", expert_result)

    for task in plan:
        if task["status"] == "pending":
            return {
                "plan": plan,
                "current_subtask": task["id"],
                "next_agent": task["agent"],
                "supervisor_round": round_count,
            }

    return {
        "plan": plan,
        "next_agent": "summarize",
        "supervisor_round": round_count,
    }


# --- 通用专家执行节点 ---

def _run_expert(expert_app, state: MultiAgentState, max_steps: int = 6) -> dict:
    """通用专家执行：运行专家子图，只将最终摘要返回给主图。"""
    from src.core.memory import load_tool_context
    plan = state.get("plan", [])
    current_id = state.get("current_subtask", "")
    # 重新加载最新的 tool_context，确保后续专家能看到前面专家保存的工具结果
    fresh_tool_context = load_tool_context(state.get("session_id", ""))
    task_desc = _build_expert_task_description(
        plan,
        current_id,
        fresh_tool_context,
        state.get("current_task", ""),
    )

    expert_state = {
        "messages": [],
        "task_description": task_desc,
        "space_id": state["space_id"],
        "user_id": state["user_id"],
        "session_id": state["session_id"],
        "step_count": 0,
        "max_steps": max_steps,
    }
    result = expert_app.invoke(expert_state)

    # 只取专家的最终回复，不把内部 tool_call/tool_result 带入主图
    expert_answer = ""
    for m in reversed(result["messages"]):
        if isinstance(m, dict) and m.get("role") == "assistant" and m.get("content"):
            expert_answer = m["content"]
            break

    return {"messages": [{"role": "assistant", "content": expert_answer}]}


def searcher_node(state: MultiAgentState) -> dict:
    return _run_expert(searcher_app, state, max_steps=6)


def editor_node(state: MultiAgentState) -> dict:
    return _run_expert(editor_app, state, max_steps=4)


def analyst_node(state: MultiAgentState) -> dict:
    return _run_expert(analyst_app, state, max_steps=4)


# --- Summarize 节点 ---

def summarize_node(state: MultiAgentState) -> dict:
    """汇总所有专家结果，生成最终中文回答。"""
    direct_answer = _single_direct_result(state)
    if direct_answer:
        return {
            "messages": [{"role": "assistant", "content": direct_answer}],
            "final_answer": direct_answer,
        }

    client = get_llm_client()
    summary_parts = []
    for task in state.get("plan", []):
        summary_parts.append(f"[{task['agent']}] {task['description']}: {task.get('result', '未完成')}")

    summary = "\n".join(summary_parts)
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=_normalize_messages([
            {"role": "system", "content": "根据以下专家执行结果，用中文给用户一个清晰的总结。搜图结果中包含 url 和 id 时，输出格式：![名称](url)  [查看详情](/picture/{id})。不要截断、改写或省略 markdown 图片链接中的 url。"},
            {"role": "user", "content": f"任务执行结果：\n{summary}"},
        ]),
    )
    content = response.choices[0].message.content or "任务已完成。"
    return {
        "messages": [{"role": "assistant", "content": content}],
        "final_answer": content,
    }


def _single_direct_result(state: MultiAgentState) -> str:
    plan = state.get("plan", [])
    if len(plan) != 1:
        return ""
    task = plan[0]
    result = task.get("result", "")
    if task.get("status") != "done":
        return ""
    if task.get("agent") == "searcher" and "![" in result and "](" in result:
        return result
    if task.get("agent") == "analyst" and result:
        return result
    return ""


# --- 路由 ---

def route_supervisor(state: MultiAgentState) -> Literal["searcher", "editor", "analyst", "summarize"]:
    return state["next_agent"]


# --- 主图构建 ---

def build_multi_agent():
    graph = StateGraph(MultiAgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("searcher", searcher_node)
    graph.add_node("editor", editor_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("summarize", summarize_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges("supervisor", route_supervisor, {
        "searcher": "searcher",
        "editor": "editor",
        "analyst": "analyst",
        "summarize": "summarize",
    })

    graph.add_edge("searcher", "supervisor")
    graph.add_edge("editor", "supervisor")
    graph.add_edge("analyst", "supervisor")
    graph.add_edge("summarize", END)

    return graph.compile()


multi_agent_app = build_multi_agent()


# --- 执行入口 ---

def _save_messages(session_id: str, new_messages: list, user_id: int = 0, space_id: str = "", task: str = ""):
    """保存对话历史（合并旧历史 + 去重 + 可选压缩）。"""
    from src.core.memory import load_messages, save_messages, save_summary
    from src.core.compact import should_compact, build_compact_prompt
    from src.service.context_persistence import persist_session_summary

    old_messages = [m for m in load_messages(session_id) if m.get("role") != "system"]
    merged = old_messages + list(new_messages)

    cleaned = []
    for m in merged:
        if cleaned and cleaned[-1].get("content") == m.get("content") and cleaned[-1].get("role") == m.get("role"):
            continue
        cleaned.append(m)

    if should_compact(cleaned):
        try:
            client = get_llm_client()
            summary = client.chat.completions.create(
                model=settings.llm_model,
                messages=_normalize_messages(build_compact_prompt(cleaned)),
            ).choices[0].message.content or ""
            if summary:
                save_summary(session_id, summary)
                persist_session_summary(session_id, user_id, space_id, task[:50], summary)
                cleaned = cleaned[-12:]
        except Exception as e:
            logger.warning(f"Compact summary failed: {e}")

    save_messages(session_id, cleaned)


def run_multi_agent(task: str, session_id: str, space_id: str, max_steps: int = 10, user_id: int = 0) -> dict:
    """同步执行多智能体任务。"""
    from src.core.memory import load_tool_context
    tool_context = load_tool_context(session_id)

    state = {
        "messages": [],
        "step_count": 0,
        "final_answer": "",
        "space_id": space_id,
        "user_id": user_id,
        "max_steps": max_steps,
        "session_id": session_id,
        "current_task": task,
        "tool_context": tool_context,
        "plan": [],
        "current_subtask": "",
        "next_agent": "",
        "supervisor_round": 0,
    }

    result = multi_agent_app.invoke(state, {"recursion_limit": max_steps * 8})
    _save_messages(session_id, result["messages"], user_id, space_id, task)
    return {"answer": result.get("final_answer", ""), "steps": result.get("supervisor_round", 0)}


async def run_multi_agent_stream(task: str, session_id: str, space_id: str, max_steps: int = 10, user_id: int = 0):
    """流式执行多智能体任务。兼容现有 SSE 事件类型。"""
    from src.core.memory import load_tool_context

    tool_context = load_tool_context(session_id)

    state = {
        "messages": [],
        "step_count": 0,
        "final_answer": "",
        "space_id": space_id,
        "user_id": user_id,
        "max_steps": max_steps,
        "session_id": session_id,
        "current_task": task,
        "tool_context": tool_context,
        "plan": [],
        "current_subtask": "",
        "next_agent": "",
        "supervisor_round": 0,
    }

    final_answer = ""
    final_steps = 0
    try:
        async for event in multi_agent_app.astream_events(state, version="v2", config={"recursion_limit": max_steps * 8}):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                # Multi-agent graphs include planner/expert/summarizer model calls.
                # Only the final graph answer should be user-visible; internal
                # chunks can contain transient planning text that is not a reply.
                continue

            elif kind == "on_tool_start":
                yield f"data: {json.dumps({'type': 'tool_call', 'tool_name': event['name'], 'args': event['data'].get('input', {})})}\n\n"

            elif kind == "on_tool_end":
                output = str(event['data'].get('output', ''))[:300]
                yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': event['name'], 'result': output})}\n\n"

            elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                output = event.get("data", {}).get("output", {})
                final_steps = output.get("supervisor_round", 0)
                plan = output.get("plan", [])
                if plan:
                    plan_text = " → ".join(f"{t['agent']}「{t['description']}」" for t in plan)
                    yield f"data: {json.dumps({'type': 'plan', 'content': plan_text})}\n\n"
                fa = output.get("final_answer", "")
                if fa:
                    final_answer = fa

        if not final_answer:
            final_answer = "抱歉，处理过程中出现了问题，请稍后重试。"

        # 保存对话历史
        _save_messages(session_id, state["messages"] + [{"role": "assistant", "content": final_answer}],
                       user_id, space_id, task)
        async for chunk in _yield_answer_stream(final_answer):
            yield chunk
        yield f"data: {json.dumps({'type': 'final', 'answer': final_answer, 'steps': final_steps})}\n\n"

    except Exception as e:
        logger.error(f"Multi-agent stream error: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
