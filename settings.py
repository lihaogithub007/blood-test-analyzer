import os
from typing import Optional


def get_zhipu_api_key() -> Optional[str]:
    """
    Central place for env lookup.
    """
    return os.getenv("ZHIPUAI_API_KEY") or os.getenv("ZHIPU_API_KEY")

