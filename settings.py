import os
from typing import Any, Dict, Optional

from database import get_llm_settings_row

DEFAULT_LLM_API_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
DEFAULT_LLM_MODEL = "glm-4v-flash"
DEFAULT_LLM_TEMPERATURE = 0.1


def get_zhipu_api_key() -> Optional[str]:
    return os.getenv("ZHIPUAI_API_KEY") or os.getenv("ZHIPU_API_KEY")

def get_admin_password() -> Optional[str]:
    pw = os.getenv("ADMIN_PASSWORD")
    pw = (pw or "").strip()
    return pw or None


def get_effective_llm_config() -> Dict[str, Any]:
    """
    合并环境变量与数据库中的页面配置：数据库非空字段覆盖环境变量/默认值。
    """
    env_key = get_zhipu_api_key()
    row = get_llm_settings_row()
    db_key = row.get("api_key") if row else None

    api_key = (db_key or "").strip() or env_key
    api_base_url = (row.get("api_base_url") or "").strip() or DEFAULT_LLM_API_BASE_URL
    model = (row.get("model") or "").strip() or DEFAULT_LLM_MODEL
    temp = row.get("temperature")
    if temp is None:
        temperature = DEFAULT_LLM_TEMPERATURE
    else:
        try:
            temperature = float(temp)
        except (TypeError, ValueError):
            temperature = DEFAULT_LLM_TEMPERATURE

    return {
        "api_key": api_key,
        "api_base_url": api_base_url,
        "model": model,
        "temperature": temperature,
    }


def get_llm_settings_for_api() -> Dict[str, Any]:
    """供 GET /api/settings/llm 使用：不返回密钥明文。"""
    row = get_llm_settings_row()
    eff = get_effective_llm_config()
    has_stored = bool(row.get("api_key") and str(row.get("api_key")).strip())
    return {
        "api_base_url": eff["api_base_url"],
        "model": eff["model"],
        "temperature": eff["temperature"],
        "has_stored_api_key": has_stored,
    }
