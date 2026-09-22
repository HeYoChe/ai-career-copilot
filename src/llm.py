
"""统一的 LLM 调用封装。

设计原则（对应当前项目需求）：
1. 没有 API Key 时，整个应用必须照常可用 —— 所以这里只负责「调用」，
   由调用方决定是否降级到离线模板模式；
2. 支持 OpenAI 兼容接口（OpenAI / DeepSeek / 通义 / Moonshot / 本地 vLLM 等），
   通过 OPENAI_BASE_URL 指定；
3. 任何异常都抛出 LLMError，附带可读的中文原因，方便 UI 直接展示。
"""

from __future__ import annotations

import os
from typing import List, Optional

try:  # python-dotenv 是可选的，缺失也不影响
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


class LLMError(RuntimeError):
    """LLM 调用失败。message 直接面向用户展示。"""


DEFAULT_MODEL = "gpt-4o-mini"


def resolve_config(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """合并「界面输入 > 环境变量 > 默认值」三级配置。"""
    key = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    url = (base_url or os.getenv("OPENAI_BASE_URL") or "").strip()
    mdl = (model or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL).strip()
    return {"api_key": key, "base_url": url or None, "model": mdl or DEFAULT_MODEL}


def is_configured(config: dict) -> bool:
    return bool(config.get("api_key"))


def chat(
    messages: List[dict],
    config: dict,
    temperature: float = 0.4,
    max_tokens: int = 1500,
) -> str:
    """调用 OpenAI 兼容的 chat.completions 接口，返回纯文本。"""
    if not is_configured(config):
        raise LLMError("未配置 API Key，已切换到「基础模式」。")

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover
        raise LLMError(f"未安装 openai 库：{exc}") from exc

    try:
        client = OpenAI(api_key=config["api_key"], base_url=config.get("base_url"))
        resp = client.chat.completions.create(
            model=config["model"],
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            raise LLMError("模型返回了空内容。")
        return content
    except LLMError:
        raise
    except Exception as exc:  # 网络、鉴权、额度、模型名错误等
        raise LLMError(f"调用失败：{type(exc).__name__} - {exc}") from exc
