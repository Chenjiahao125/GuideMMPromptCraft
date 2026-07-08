import os
from dotenv import load_dotenv
from zhipuai import ZhipuAI
from langchain_core.language_models.llms import LLM
from typing import List, Optional

# 加载环境变量
load_dotenv()
api_key = os.getenv("ZHIPU_API_KEY")

if not api_key:
    raise ValueError("请在 .env 文件中配置 ZHIPU_API_KEY")

client = ZhipuAI(api_key=api_key)

class CompatibleZhipuLLM(LLM):
    """精简版智谱AI LLM封装，仅保留核心功能"""
    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        try:
            response = client.chat.completions.create(
                model="glm-4-flash",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"❌ LLM调用失败：{str(e)}"

    @property
    def _llm_type(self) -> str:
        return "zhipu"

# 初始化大模型（删除无用embeddings）
llm = CompatibleZhipuLLM()