# core/guided_question_flow.py
import re
from typing import Dict, Any, List, Literal, TypedDict, Optional
from langgraph.graph import StateGraph, END
from core.llm_config import llm


# ========== 1. 状态定义 ==========
class AgentState(TypedDict):
    prompt_type: str
    messages: List[Dict[str, str]]
    reply: str
    finished: bool
    collected: Dict[str, Any]
    current_question_index: int


# ========== 2. 强制收集维度配置 ==========
VIDEO_DIMENSIONS = [
    {"name": "角色类型", "question": "视频中的主要角色是什么类型？（例如：人类、妖怪、动物、机器人、神明、外星人等）",
     "required": True},
    {"name": "角色性别", "question": "角色的性别是什么？（男 / 女 / 无性别 / 未知）", "required": True},
    {"name": "主要场景",
     "question": "视频的主要场景在哪里？（例如：城市、山林、沙漠、海洋、天空、科幻基地、古代城镇、奇幻世界、室内等）",
     "required": True},
    {"name": "核心动作", "question": "视频的核心动作是什么？（例如：打斗、变身、奔跑、对话、情感表达、特效展示等）",
     "required": True},
    {"name": "时长", "question": "视频的时长是多少秒？请输入数字（例如：10、30）", "required": True},
    {"name": "画质要求", "question": "希望的画质是什么？（例如：2K、4K、8K、自然光影、胶片质感）", "required": True},
    {"name": "视觉风格", "question": "想要的视觉风格是什么？（例如：3D国漫、电商产品、户外写实、科幻特效、生活vlog）",
     "required": True},
    {"name": "特殊效果", "question": "需要哪些特殊效果？（例如：魔法、雷电、烟雾、光效、爆炸，可多选用“和”连接）",
     "required": False},
    {"name": "额外说明", "question": "还有其他需要补充的细节吗？（没有就说“无”）", "required": False},
]

IMAGE_DIMENSIONS = [
    {"name": "主题", "question": "图片的主题是什么？", "required": True},
    {"name": "风格", "question": "想要的风格是什么？", "required": True},
    {"name": "构图", "question": "希望的构图方式？", "required": False},
]

COPY_DIMENSIONS = [
    {"name": "文案类型", "question": "文案类型是什么？（电商/短视频/海报）", "required": True},
    {"name": "商品/主题", "question": "涉及的商品或主题是什么？", "required": True},
    {"name": "目标人群", "question": "目标受众是谁？", "required": False},
    {"name": "语气风格", "question": "希望的语气风格？", "required": False},
]


def is_valid_value(value: str, dim: Dict) -> bool:
    """检查用户输入是否有效（非空、不是无意义单字符）"""
    if not value or value.strip() == "":
        return False
    # 允许“随便”作为跳过
    if value.strip() in ["随便", "跳过", "无", "未知"]:
        return True
    # 对于时长，必须包含数字
    if dim["name"] == "时长":
        if re.search(r"\d+", value):
            return True
        return False
    # 一般要求长度至少2个字符（排除“1”、“a”等）
    if len(value.strip()) < 2:
        return False
    return True


def extract_field_value(user_input: str, dim: Dict) -> Optional[str]:
    """从用户输入中提取字段值（直接使用用户输入，只做清洗）"""
    cleaned = user_input.strip()
    if cleaned in ["随便", "跳过", "无", "未知"]:
        return "随便"
    # 对于时长，提取数字并加“秒”
    if dim["name"] == "时长":
        nums = re.findall(r"\d+", cleaned)
        if nums:
            return f"{nums[0]}秒"
        return None
    return cleaned


def build_question(dim: Dict) -> str:
    return dim["question"]


# ========== 3. 节点函数 ==========
def node_start(state: AgentState) -> AgentState:
    prompt_type = state["prompt_type"]
    if prompt_type == "video":
        dims = VIDEO_DIMENSIONS
        greeting = "你好！我是灵构助手，可以帮你生成详细的视频提示词。接下来我会逐项询问细节，请尽量详细回答。如果某个问题不清楚，可以回复“随便”跳过。"
    elif prompt_type == "image":
        dims = IMAGE_DIMENSIONS
        greeting = "你好！我是灵构助手，可以帮你生成图片提示词。请跟随我的问题提供细节。"
    else:
        dims = COPY_DIMENSIONS
        greeting = "你好！我是灵构助手，可以帮你生成文案提示词。请回答以下问题。"

    collected = {}
    current_idx = 0
    first_question = build_question(dims[0])
    reply = f"{greeting}\n\n{first_question}"
    return {
        **state,
        "reply": reply,
        "finished": False,
        "collected": collected,
        "current_question_index": current_idx
    }


def node_collect(state: AgentState) -> AgentState:
    prompt_type = state["prompt_type"]
    dims = {
        "video": VIDEO_DIMENSIONS,
        "image": IMAGE_DIMENSIONS,
        "copy": COPY_DIMENSIONS
    }.get(prompt_type, [])
    if not dims:
        return {**state, "finished": True, "reply": "无法处理该类型"}

    idx = state.get("current_question_index", 0)
    if idx >= len(dims):
        return {**state, "finished": True, "reply": "所有信息已收集完成，正在生成..."}

    # 获取最后一条用户消息
    last_user_msg = ""
    for m in reversed(state.get("messages", [])):
        if m["role"] == "user":
            last_user_msg = m["content"]
            break

    current_dim = dims[idx]
    value = extract_field_value(last_user_msg, current_dim)

    # 验证有效性
    if value is None or (current_dim.get("required", False) and not is_valid_value(value, current_dim)):
        # 无效输入，重新问同一个问题
        reply = f"您的回答似乎不够明确。{current_dim['question']}"
        return {**state, "reply": reply, "finished": False}

    # 保存有效值
    collected = state.get("collected", {}).copy()
    collected[current_dim["name"]] = value
    next_idx = idx + 1

    if next_idx >= len(dims):
        return {
            **state,
            "collected": collected,
            "finished": True,
            "reply": "所有信息已收集完成，正在为您生成提示词..."
        }
    else:
        next_question = build_question(dims[next_idx])
        return {
            **state,
            "collected": collected,
            "current_question_index": next_idx,
            "reply": next_question,
            "finished": False
        }


def node_generate(state: AgentState) -> AgentState:
    from core.prompt_generator import PromptGenerator
    generator = PromptGenerator()
    collected = state.get("collected", {})

    # 构建详细摘要
    summary_parts = []
    for k, v in collected.items():
        if v and v != "随便":
            summary_parts.append(f"{k}: {v}")
    summary = "；".join(summary_parts)

    # 提取时长数字
    duration = 0
    if "时长" in collected and collected["时长"]:
        nums = re.findall(r"\d+", collected["时长"])
        if nums:
            duration = int(nums[0])
    if duration <= 0 and state["prompt_type"] == "video":
        duration = 10  # 默认10秒

    user_answers = {
        "prompt_type": state["prompt_type"],
        "match_type": collected.get("视觉风格", "3D国漫"),
        "round1": summary,
        "round2": "",
        "round3": "",
        "duration": duration
    }
    full_prompt = generator.build_prompt(user_answers)
    reply = f"🎉 生成完成！\n{full_prompt}"
    return {**state, "reply": reply, "finished": True}


def route_after_collect(state: AgentState) -> Literal["collect", "generate"]:
    return "generate" if state.get("finished") else "collect"


def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("start", node_start)
    workflow.add_node("collect", node_collect)
    workflow.add_node("generate", node_generate)
    workflow.set_entry_point("start")
    workflow.add_edge("start", "collect")
    workflow.add_conditional_edges("collect", route_after_collect, {
        "collect": "collect",
        "generate": "generate"
    })
    workflow.add_edge("generate", END)
    return workflow.compile()


class GuidedQuestionFlow:
    def __init__(self):
        self.graph = build_graph()

    def build_graph(self):
        return self.graph

    def process(self, stage: int, user_answers: dict, user_input: str, prompt_type: str = "video"):
        if "langgraph_state" in user_answers:
            state = user_answers["langgraph_state"]
            state.setdefault("prompt_type", prompt_type)
            state.setdefault("messages", [])
            state.setdefault("reply", "")
            state.setdefault("finished", False)
            state.setdefault("collected", {})
            state.setdefault("current_question_index", 0)
        else:
            state = {
                "prompt_type": prompt_type,
                "messages": [],
                "reply": "",
                "finished": False,
                "collected": {},
                "current_question_index": 0
            }

        state["messages"].append({"role": "user", "content": user_input})

        if len(state["messages"]) == 1:
            state = node_start(state)
            state = node_collect(state)
        else:
            state = node_collect(state)

        if state.get("finished"):
            if "generated" not in state:
                state = node_generate(state)
                state["generated"] = True
            new_stage = 4
            new_answers = {}
            reply = state["reply"]
        else:
            new_stage = 1
            new_answers = user_answers.copy()
            new_answers["langgraph_state"] = state
            for k, v in state.get("collected", {}).items():
                new_answers[k] = v
            reply = state["reply"]

        return reply, new_stage, new_answers