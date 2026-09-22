
"""PDF 简历解析与文本清洗。"""

from __future__ import annotations

import re

import pdfplumber


def read_pdf(file_like_or_path):
    """接受 Streamlit 上传的文件对象（BytesIO）或本地路径，返回带换行的原始文本。"""
    text = []
    source = file_like_or_path
    if hasattr(file_like_or_path, "read"):
        file_like_or_path.seek(0)  # Streamlit UploadedFile
    with pdfplumber.open(source) as pdf:
        for page in pdf.pages:
            text.append(page.extract_text() or "")
    return "\n".join(text)


def clean_text(t: str) -> str:
    """把文本压成单行，用于 embedding 与关键词匹配。"""
    t = t or ""
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_lines(t: str) -> str:
    """保留换行的轻度清洗，用于需要「按行」判断的场景（如抽取项目名、bullet）。"""
    t = (t or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t\u3000]+", " ", line).strip() for line in t.split("\n")]
    return "\n".join(line for line in lines if line)


_BULLET_NOISE = re.compile(
    r"@|^\+?\d[\d\s\-]{6,}|"
    r"(university|college|institute|school|大学|学院|专业|学号|GPA)",
    re.I,
)


def extract_bullets(resume_raw: str, limit: int = 12) -> list:
    """从简历中粗抽「经历描述」句子，供简历优化模块挑选。

    过滤掉：联系方式行、教育背景行、技能清单行（逗号过多）、章节标题行。
    """
    bullets = []
    seen = set()
    for line in normalize_lines(resume_raw).split("\n"):
        stripped = re.sub(r"^[\-•*·▪●○–—\d\.、\)\(]+\s*", "", line).strip()
        if not (12 <= len(stripped) <= 160):
            continue
        if _BULLET_NOISE.search(stripped):
            continue
        if stripped.count(",") + stripped.count("、") >= 3:  # 技能罗列行，不是经历
            continue
        # 单词数太少的短标题（如 "Voting System Platform"）不算描述句
        if len(stripped.split()) < 4 and not re.search(r"[\u4e00-\u9fff]", stripped):
            continue
        if stripped.isupper():
            continue
        if stripped in seen:
            continue
        seen.add(stripped)
        bullets.append(stripped)
        if len(bullets) >= limit:
            break
    return bullets
