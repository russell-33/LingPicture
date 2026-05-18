from typing import TypedDict, Annotated
import operator


class SubTask(TypedDict):
    id: str
    description: str
    agent: str              # "searcher" | "editor" | "analyst"
    status: str             # "pending" | "done" | "failed"
    result: str


class MultiAgentState(TypedDict):
    messages: Annotated[list[dict], operator.add]
    session_id: str
    current_task: str
    tool_context: dict
    space_id: str
    user_id: int
    step_count: int
    max_steps: int
    final_answer: str
    plan: list[SubTask]            # 当前任务计划
    current_subtask: str           # 正在执行的子任务 ID
    next_agent: str                # 路由目标: "searcher"|"editor"|"analyst"|"summarize"
    supervisor_round: int          # Supervisor 当前轮次（防无限循环）


class ExpertState(TypedDict):
    messages: list[dict]
    task_description: str
    space_id: str
    user_id: int
    session_id: str
    step_count: int
    max_steps: int
