
"""句向量：把简历/JD 文本转成 embedding。

- 默认模型 `all-MiniLM-L6-v2`（体积小、英文效果好、CPU 秒级）；
- 中文简历/中文 JD 建议换 `paraphrase-multilingual-MiniLM-L12-v2`（需额外下载约 470MB）；
- 模型按名字缓存，切换模型不会重复加载旧模型。
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np

DEFAULT_MODEL = "all-MiniLM-L6-v2"
MULTILINGUAL_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

_models: dict = {}


def current_model_name(model_name: Optional[str] = None) -> str:
    return (model_name or os.getenv("EMBED_MODEL") or DEFAULT_MODEL).strip()


def get_model(model_name: Optional[str] = None):
    """加载句向量模型：优先用本地缓存（离线可用），缓存缺失时才联网下载。"""
    name = current_model_name(model_name)
    if name in _models:
        return _models[name]

    from sentence_transformers import SentenceTransformer  # 延迟导入，加快启动

    try:
        # 关键：先强制离线加载。缓存里已经有模型的用户（比如断网/内网环境）
        # 就不会因为 transformers 联网校验失败而整个应用报错。
        _models[name] = SentenceTransformer(name, local_files_only=True)
    except Exception:
        # 本地没有缓存，退回到联网下载
        _models[name] = SentenceTransformer(name)
    return _models[name]


def embed_single(text: str, model_name: Optional[str] = None) -> np.ndarray:
    model = get_model(model_name)
    vec = model.encode([text], normalize_embeddings=True)[0]
    return vec
