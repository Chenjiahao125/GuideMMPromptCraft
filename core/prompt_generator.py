# core/prompt_generator.py
import re
import yaml
from langchain_core.prompts import PromptTemplate
from core.llm_config import llm


class PromptGenerator:
    def __init__(self):
        try:
            with open("./core/multimodal_templates.yaml", "r", encoding="utf-8") as f:
                self.lib = yaml.safe_load(f)
        except Exception as e:
            raise FileNotFoundError(f"配置文件加载失败：{e}")

        self.video_template = PromptTemplate(
            input_variables=["frame", "param", "style", "camera", "user_info", "time_slice"],
            template="""
你是专业AI视频提示词工程师。请严格遵循用户要求，输出结构化的视频提示词。

【模块列表】：{frame}
【专业参数参考】：{param}
【风格特效参考】：{style}
【运镜节奏参考】：{camera}
【用户需求】：{user_info}
【视频总时长】：{time_slice} 秒

⚠️ 强制输出格式（每个模块一行，不要有多余解释）：
**核心**：总结视频的核心概念（风格、背景、氛围等）。
**画面**：完全按照用户提供的画质要求（例如用户要求2K就写2K，禁止擅自升级），并描述画面质感、光效等。
**人物**：根据用户给出的角色类型、性别等，详细描述外貌、服饰、妆容。
**分镜**：根据视频内容和总时长，自然地拆分镜头。每个镜头时长建议2-5秒，禁止按每秒一段。镜头数量应合理（例如10秒视频通常2-4个镜头）。格式：「镜头X（起始秒-结束秒）：详细画面描述 + 角色动作 + 台词（如果有）」。
**音效层**：列出关键音效。
**配音层**：描述配音风格（如TVB腔、无配音等）。

⚠️ 铁律：
1. 用户要求2K画质，严禁写成4K或8K；用户要求胶片质感，则不得写成超清。
2. 分镜必须贴合用户描述的核心动作和场景，不得凭空编造不相关的情节。
3. 每个分镜描述必须详细（30字以上），包含角色情绪、环境细节、动作过程。
4. 总时长必须严格等于 {time_slice} 秒，分镜时间连续覆盖全片。
5. 禁止输出任何与用户需求矛盾的内容。
"""
        )

        self.image_template = PromptTemplate(
            input_variables=["frame", "param", "style", "composition", "user_info"],
            template="""
你是专业AI图片提示词工程师，严格按照以下规则生成：

【模块列表】：{frame}
【专业参数参考】：{param}
【风格参考】：{style}
【构图参考】：{composition}
【用户需求】：{user_info}

⚠️ 强制规则：
1. 按模块列表顺序输出，每个模块单独一行。
2. 贴合用户需求，禁止随意更改用户指定的风格、画质。
3. 输出纯提示词，无解释。
"""
        )

        self.copy_template = PromptTemplate(
            input_variables=["user_info", "match_type"],
            template="""
你是专业文案策划。严格根据用户需求生成纯文案。

【用户需求】：{user_info}
【文案类型】：{match_type}

输出要求：
- 电商文案：种草话术
- 短视频脚本：镜头+台词
- 海报文案：主标题+副标题+slogan
直接输出文案，每行一条，无解释。
"""
        )

    def get_time_slice(self, user_answers: dict) -> int:
        if "duration" in user_answers and user_answers["duration"]:
            try:
                return int(user_answers["duration"])
            except:
                pass
        text = user_answers.get("round1", "")
        if text:
            nums = re.findall(r"\d+", str(text))
            if nums:
                return int(nums[0])
        return 5

    def build_prompt(self, user_answers: dict) -> str:
        prompt_type = user_answers.get("prompt_type", "video")
        match_type = user_answers.get("match_type", "电商产品")
        round1 = user_answers.get("round1", "")
        round2 = user_answers.get("round2", "")
        round3 = user_answers.get("round3", "")

        def auto_fill(text, default=""):
            if not text or text.strip() in ["不知道", "随便", "无", ""]:
                return default
            return text.strip()

        user_info = f"{auto_fill(round1)} {auto_fill(round2)} {auto_fill(round3)}".strip()

        try:
            if prompt_type == "video":
                frame_list = self.lib["video_frame"].get(match_type, self.lib["video_frame"]["3D国漫"])
                param_list = self.lib["param_words"].get(match_type, self.lib["param_words"]["3D国漫"])
                style_list = self.lib["style_words"].get(match_type, self.lib["style_words"]["3D国漫"])
                camera_list = self.lib["camera_words"].get(match_type, self.lib["camera_words"]["3D国漫"])

                chain = self.video_template | llm
                time_slice = self.get_time_slice(user_answers)
                res = chain.invoke({
                    "frame": "、".join(frame_list),
                    "param": "、".join(param_list),
                    "style": "、".join(style_list),
                    "camera": "、".join(camera_list),
                    "user_info": user_info,
                    "time_slice": time_slice
                })
                return str(res)

            elif prompt_type == "image":
                frame_list = self.lib["image_frame"].get(match_type, self.lib["image_frame"]["电商产品"])
                param_list = self.lib["image_param"].get(match_type, self.lib["image_param"]["电商产品"])
                style_list = self.lib["image_style"].get(match_type, self.lib["image_style"]["电商产品"])
                composition_list = self.lib["composition_words"].get(match_type, self.lib["composition_words"]["电商产品"])

                chain = self.image_template | llm
                res = chain.invoke({
                    "frame": "、".join(frame_list),
                    "param": "、".join(param_list),
                    "style": "、".join(style_list),
                    "composition": "、".join(composition_list),
                    "user_info": user_info
                })
                return str(res)

            elif prompt_type == "copy":
                chain = self.copy_template | llm
                res = chain.invoke({
                    "user_info": user_info,
                    "match_type": match_type
                })
                return str(res)

            else:
                return "❌ 不支持的提示词类型"
        except Exception as e:
            return f"❌ 生成失败：{str(e)}"