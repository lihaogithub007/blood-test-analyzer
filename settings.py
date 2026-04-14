import os
from typing import Any, Dict, Optional

DEFAULT_LLM_API_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
DEFAULT_LLM_MODEL = "glm-4v-flash"
DEFAULT_LLM_TEMPERATURE = 0.1


def get_zhipu_api_key() -> Optional[str]:
    return os.getenv("ZHIPUAI_API_KEY") or os.getenv("ZHIPU_API_KEY")


def get_effective_llm_config() -> Dict[str, Any]:
    """
    从环境变量读取大模型配置（.env）。
    - api_key: ZHIPUAI_API_KEY / ZHIPU_API_KEY
    - api_base_url: LLM_API_BASE_URL (默认智谱 OpenAI 兼容接口)
    - model: LLM_MODEL (默认 glm-4v-flash)
    - temperature: LLM_TEMPERATURE (默认 0.1)
    """
    api_key = get_zhipu_api_key()

    api_base_url = (os.getenv("LLM_API_BASE_URL") or "").strip() or DEFAULT_LLM_API_BASE_URL
    model = (os.getenv("LLM_MODEL") or "").strip() or DEFAULT_LLM_MODEL

    t_raw = os.getenv("LLM_TEMPERATURE")
    if t_raw is None or str(t_raw).strip() == "":
        temperature = DEFAULT_LLM_TEMPERATURE
    else:
        try:
            temperature = float(str(t_raw).strip())
        except (TypeError, ValueError):
            temperature = DEFAULT_LLM_TEMPERATURE

    return {
        "api_key": api_key,
        "api_base_url": api_base_url,
        "model": model,
        "temperature": temperature,
    }
