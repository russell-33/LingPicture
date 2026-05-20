import json
import logging
import re
from typing import Literal, Callable, Set, Optional

from langgraph.graph import StateGraph, END
from src.core.multi_agent_state import ExpertState
from src.core.picture_id_utils import extract_picture_ids_from_text
from src.core.tag_utils import extract_add_tag, extract_remove_tag, normalize_tag
from src.service.llm import get_llm_client, _normalize_messages
from src.core.tool import get_tools_list, execute_tool
from src.config import settings

logger = logging.getLogger(__name__)

TOOL_RESULT_MAX_CHARS = 8000
SEARCH_DESCRIPTION_MAX_CHARS = 240


def _clip_text_at_line_boundary(text: str, max_chars: int = TOOL_RESULT_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars]
    newline_index = clipped.rfind("\n")
    if newline_index > max_chars * 0.6:
        clipped = clipped[:newline_index]
    return clipped.rstrip() + "\n...（内容过长，已省略后续内容）"


def _compact_search_result(raw_result: str, max_chars: int = TOOL_RESULT_MAX_CHARS) -> str:
    try:
        data = json.loads(raw_result)
    except json.JSONDecodeError:
        return _clip_text_at_line_boundary(raw_result, max_chars)

    if not isinstance(data, list):
        return _clip_text_at_line_boundary(raw_result, max_chars)

    compact_items = []
    for item in data:
        if not isinstance(item, dict):
            continue
        compact = {}
        for key in ("id", "name", "url", "description", "score"):
            if key not in item or item.get(key) is None:
                continue
            value = item.get(key)
            if key == "description":
                value = str(value)
                if len(value) > SEARCH_DESCRIPTION_MAX_CHARS:
                    value = value[:SEARCH_DESCRIPTION_MAX_CHARS].rstrip() + "..."
            compact[key] = value

        candidate = json.dumps(compact_items + [compact], ensure_ascii=False)
        if len(candidate) > max_chars:
            if compact_items:
                break
            compact.pop("description", None)
            candidate = json.dumps([compact], ensure_ascii=False)
            if len(candidate) > max_chars:
                return _clip_text_at_line_boundary(candidate, max_chars)
        compact_items.append(compact)

    return json.dumps(compact_items, ensure_ascii=False)


def _format_tool_result_for_message(name: str, result: str) -> str:
    raw_result = str(result)
    if name in {"search_pictures_by_semantic", "search_pictures_by_tag"}:
        return _compact_search_result(raw_result)
    return _clip_text_at_line_boundary(raw_result)


def _extract_remove_tag_from_task(task_description: str) -> str:
    return extract_remove_tag(task_description)


def _build_direct_edit_tool_call(state: ExpertState, tool_names: Set[str]) -> Optional[dict]:
    if "edit_picture" not in tool_names:
        return None

    task_description = state.get("task_description", "")
    picture_ids = extract_picture_ids_from_text(task_description)
    if not picture_ids:
        return None

    remove_tags = extract_remove_tag(task_description)
    add_tag = extract_add_tag(task_description)
    if not remove_tags and not add_tag:
        return None

    return {
        "id": "direct-edit-picture",
        "type": "function",
        "function": {
            "name": "edit_picture",
            "arguments": json.dumps({
                "picture_ids": ",".join(picture_ids),
                "tags": "" if remove_tags else add_tag,
                "remove_tags": remove_tags,
            }, ensure_ascii=False),
        },
    }


def _normalize_edit_picture_args(name: str, args: dict, task_description: str) -> dict:
    if name != "edit_picture":
        return args

    normalized = dict(args)
    remove_tag = _extract_remove_tag_from_task(task_description)
    if remove_tag and not normalized.get("remove_tags"):
        normalized["remove_tags"] = str(normalized.get("tags") or remove_tag)
    if remove_tag and normalize_tag(normalized.get("tags", "")) == normalize_tag(normalized.get("remove_tags", "")):
        normalized["tags"] = ""

    add_tag = extract_add_tag(task_description)
    if add_tag and not normalized.get("tags") and not normalized.get("remove_tags"):
        normalized["tags"] = add_tag
    return normalized


def _normalize_search_tool_call(name: str, args: dict, task_description: str,
                                tool_names: Set[str]) -> tuple[str, dict]:
    remove_tag = extract_remove_tag(task_description)
    if name == "search_pictures_by_tag" and remove_tag:
        normalized = dict(args)
        normalized["tag"] = remove_tag
        normalized["limit"] = max(int(normalized.get("limit", 100) or 100), 100)
        return name, normalized

    if name != "search_pictures_by_semantic":
        return name, args

    if remove_tag and "search_pictures_by_tag" in tool_names:
        return "search_pictures_by_tag", {"tag": remove_tag, "limit": 100}

    if not extract_add_tag(task_description):
        return name, args

    normalized = dict(args)
    try:
        normalized["top_k"] = max(int(normalized.get("top_k", 10)), 50)
    except (TypeError, ValueError):
        normalized["top_k"] = 50
    return name, normalized


def _format_search_result_markdown(raw_result: str) -> str:
    try:
        data = json.loads(raw_result)
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, list):
        return ""

    lines = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue
        picture_id = item.get("id") or item.get("picture_id")
        name = item.get("name") or item.get("picture_name") or f"图片{idx}"
        url = item.get("url", "")
        if url:
            line = f"{idx}. ![{name}]({url})"
        else:
            line = f"{idx}. {name}"
        if picture_id:
            line += f"  ID: {picture_id}  [查看详情](/picture/{picture_id})"
        lines.append(line)

    if not lines:
        return ""
    return "已找到相关图片：\n" + "\n".join(lines)


def _build_direct_tool_answer(state: ExpertState) -> str:
    for message in state.get("messages", []):
        if not isinstance(message, dict):
            continue
        if message.get("role") != "tool":
            continue
        content = str(message.get("content", "")).strip()
        if content.startswith(("空间分析失败：", "空间统计数据不一致：")):
            return content
        direct_answer = _format_search_result_markdown(content)
        if direct_answer:
            return direct_answer
    return ""


def make_agent_node(system_prompt: str, tool_names: Set[str]):
    """创建专家 LLM 推理节点。"""

    def _get_tools():
        all_tools = get_tools_list()
        return [t for t in all_tools if t["function"]["name"] in tool_names]

    def _build_user_message(state: ExpertState) -> str:
        return (
            f"任务：{state['task_description']}\n\n"
            "系统已完成鉴权，并提供以下可信上下文：\n"
            f"- 当前可信空间 ID: {state['space_id']}\n"
            f"- 当前可信用户 ID: {state['user_id']}\n\n"
            "调用工具时必须使用上述可信上下文。"
            "不要向用户索要空间 ID，不要编造或替换为其他空间 ID。"
        )

    def agent_node(state: ExpertState) -> dict:
        direct_edit_tool_call = _build_direct_edit_tool_call(state, tool_names)
        if direct_edit_tool_call:
            return {
                "messages": [{
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [direct_edit_tool_call],
                }],
                "step_count": state["step_count"] + 1,
            }

        client = get_llm_client()
        msgs = [{"role": "system", "content": system_prompt}]
        msgs.extend(state["messages"])
        msgs.append({"role": "user", "content": _build_user_message(state)})

        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=_normalize_messages(msgs),
            tools=_get_tools(),
            tool_choice="auto",
        )
        msg = response.choices[0].message

        new_messages = []
        if msg.tool_calls:
            tool_calls_formatted = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
            new_messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": tool_calls_formatted})
        else:
            new_messages.append({"role": "assistant", "content": msg.content or ""})

        return {"messages": new_messages, "step_count": state["step_count"] + 1}

    return agent_node


def make_should_continue(node_prefix: str):
    """创建专家 should_continue 路由函数。"""

    def should_continue(state: ExpertState) -> str:
        msgs = state["messages"]
        step = state["step_count"]
        has_tools = msgs and isinstance(msgs[-1], dict) and msgs[-1].get("tool_calls")
        if step >= state["max_steps"]:
            return f"{node_prefix}_respond"
        if has_tools:
            return f"{node_prefix}_tools"
        return f"{node_prefix}_respond"

    return should_continue


def make_after_tools_route(node_prefix: str):
    """工具执行后的路由。

    默认工具执行后直接总结。editor 如果刚执行的是 get_picture_detail，
    需要回到 agent 继续判断是否调用 edit_picture。
    """

    def after_tools(state: ExpertState) -> str:
        if state["step_count"] >= state["max_steps"]:
            return f"{node_prefix}_respond"
        if not node_prefix.startswith("editor"):
            return f"{node_prefix}_respond"

        last_tool_names = []
        for message in reversed(state.get("messages", [])):
            if not isinstance(message, dict):
                continue
            tool_calls = message.get("tool_calls")
            if tool_calls:
                last_tool_names = [
                    tc.get("function", {}).get("name", "")
                    for tc in tool_calls
                    if isinstance(tc, dict)
                ]
                break

        if last_tool_names and "edit_picture" not in last_tool_names and "get_picture_detail" in last_tool_names:
            return f"{node_prefix}_agent"
        return f"{node_prefix}_respond"

    return after_tools


def make_execute_tools(tool_names: Set[str],
                       inject_user_id_tools: Optional[Set[str]] = None,
                       persist_tools: Optional[Set[str]] = None,
                       use_memory: bool = True):
    """创建专家工具执行节点。

    Args:
        tool_names: 该专家拥有的工具名集合
        inject_user_id_tools: 需要注入 user_id 的工具集合
        persist_tools: 需要记录操作日志的工具集合
        use_memory: 是否使用 tool_context 记忆
    """
    if inject_user_id_tools is None:
        inject_user_id_tools = set()
    if persist_tools is None:
        persist_tools = set()

    def execute_tools(state: ExpertState) -> dict:
        from src.core.memory import load_tool_context, save_tool_context
        from src.core.tool_context import summarize_tool_result

        last_msg = state["messages"][-1]
        tool_calls = last_msg.get("tool_calls", [])
        tool_results = []
        session_id = state.get("session_id", "")

        for tc in tool_calls:
            name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            name, args = _normalize_search_tool_call(name, args, state.get("task_description", ""), tool_names)
            if name in tool_names:
                args["space_id"] = int(state["space_id"])
            if name in inject_user_id_tools:
                args["user_id"] = state["user_id"]
            args = _normalize_edit_picture_args(name, args, state.get("task_description", ""))

            try:
                result = execute_tool(name, args)
            except Exception as e:
                result = f"Tool execution error: {str(e)}"
                logger.error(f"Tool {name} failed: {e}")

            if session_id and use_memory:
                from src.core.tool_context import SEARCH_TOOLS, summarize_tool_result, append_search_round
                if name in SEARCH_TOOLS:
                    existing = load_tool_context(session_id)
                    summarized = summarize_tool_result(name, str(result))
                    query = args.get("query_text", "") or args.get("tag", "")
                    updated = append_search_round(existing, summarized, query)
                    save_tool_context(session_id, updated)

            if session_id and name in persist_tools:
                from src.service.context_persistence import persist_operation_log
                persist_operation_log(
                    session_id=session_id,
                    user_id=state["user_id"],
                    space_id=state["space_id"],
                    operation_type=name,
                    tool_name=name,
                    target_ids=json.dumps(args, ensure_ascii=False),
                    request_text=state.get("task_description", ""),
                    result_summary=str(result)[:1000],
                    status="SUCCESS" if not str(result).startswith("Tool execution error") else "FAILED",
                )

            tool_results.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": _format_tool_result_for_message(name, str(result)),
            })

        return {"messages": tool_results, "step_count": state["step_count"]}

    return execute_tools


def make_respond_node(system_prompt: str, summary_instruction: str):
    """创建专家回复节点。"""

    def _build_summary_message(state: ExpertState) -> str:
        lines = [
            f"任务：{state.get('task_description', '')}",
            "",
            "专家执行过程和工具结果：",
        ]
        for message in state.get("messages", []):
            if not isinstance(message, dict):
                continue
            role = message.get("role", "")
            content = str(message.get("content", "")).strip()
            if not content:
                continue
            if role == "tool":
                lines.append(f"- 工具结果：{content}")
            elif role == "assistant":
                lines.append(f"- 专家回复：{content}")
        lines.extend(["", summary_instruction])
        return "\n".join(lines)

    def respond_node(state: ExpertState) -> dict:
        direct_answer = _build_direct_tool_answer(state)
        if direct_answer:
            return {"messages": [{"role": "assistant", "content": direct_answer}]}

        client = get_llm_client()
        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _build_summary_message(state)},
        ]
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=_normalize_messages(msgs),
        )
        content = response.choices[0].message.content or "任务完成。"
        return {"messages": [{"role": "assistant", "content": content}]}

    return respond_node


def build_expert_graph(prefix: str, system_prompt: str, tool_names: Set[str],
                       inject_user_id_tools: Optional[Set[str]] = None,
                       persist_tools: Optional[Set[str]] = None,
                       summary_instruction: str = "请总结执行结果。"):
    """构建通用专家子图。

    Args:
        prefix: 节点名前缀，如 "searcher"、"editor"、"analyst"
        system_prompt: 专家 system prompt
        tool_names: 专家工具名集合
        inject_user_id_tools: 需要注入 user_id 的工具
        persist_tools: 需要记录操作日志的工具
        summary_instruction: 回复节点的总结指令
    """
    graph = StateGraph(ExpertState)

    graph.add_node(f"{prefix}_agent", make_agent_node(system_prompt, tool_names))
    graph.add_node(f"{prefix}_tools", make_execute_tools(tool_names, inject_user_id_tools, persist_tools))
    graph.add_node(f"{prefix}_respond", make_respond_node(system_prompt, summary_instruction))

    graph.set_entry_point(f"{prefix}_agent")

    graph.add_conditional_edges(f"{prefix}_agent", make_should_continue(prefix), {
        f"{prefix}_tools": f"{prefix}_tools",
        f"{prefix}_respond": f"{prefix}_respond",
    })
    graph.add_conditional_edges(f"{prefix}_tools", make_after_tools_route(prefix), {
        f"{prefix}_agent": f"{prefix}_agent",
        f"{prefix}_respond": f"{prefix}_respond",
    })
    graph.add_edge(f"{prefix}_respond", END)

    return graph.compile()
