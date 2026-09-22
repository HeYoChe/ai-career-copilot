
"""离线改写模板（无需 API Key 也能用）。

设计要点：
1. 模板语言**跟随输入** —— 要改写的简历原文是中文就给中文句式，是英文才给英文句式。
   （中文简历配英文 JD 时，改写结果仍应是中文，所以优先看简历原文。）
2. 英文模板里不能夹中文技能名：词典里有英文别名的取英文别名，
   例如「摄像头」→ camera、「图像处理」→ image processing、「沟通表达」→ communication。
3. 模板只给句式骨架（用 [方括号] 留空），不替用户编造事实 —— 项目红线。
"""

from __future__ import annotations

import re
from typing import List, Optional

from src.skills import SKILL_TAXONOMY

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_ASCII_ONLY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 +#./\-]*$")

# 中文句式模板
_ZH_PATTERNS = [
    "围绕「{kw}」写结果：在 [项目/任务] 中用 {kw} 完成了 [具体功能]，[指标] 从 A 提升到 B。",
    "用「{kw}」补短板：动词开头（搭建 / 优化 / 上线）+ [对象]，用 {kw} 解决了 [什么痛点]，最终 [量化结果]。",
    "把「{kw}」写成技术选型：为了 [目标] 选择 {kw}，相比 [旧方案] 的差异是 [效果]，量化后 [结果]。",
]

# 英文句式模板
_EN_PATTERNS = [
    "Highlight impact with '{kw}': Achieved X% improvement by applying {kw} to [project/task].",
    "Show ownership with '{kw}': Built [feature] with {kw}, cutting [metric] from A to B.",
    "Frame '{kw}' as a decision: Chose {kw} for [goal]; it beat [alternative] on [tradeoff].",
]

_ZH_FALLBACK = (
    "给结果加量化（%、节省的时间、降低的错误率），用动词开头（搭建 / 优化 / 上线 / 重构），"
    "先写做了什么、再写带来什么变化。"
)
_EN_FALLBACK = (
    "Quantify results (%, time saved, errors reduced) and lead with strong verbs "
    "(Built, Optimized, Deployed), then state the outcome."
)


def detect_lang(*texts: str) -> str:
    """粗略判断语言：中文出现得够多就返回 "zh"，否则返回 "en"。"""
    cjk = latin = 0
    for t in texts:
        if not t:
            continue
        cjk += len(_CJK_RE.findall(t))
        latin += len(_LATIN_WORD_RE.findall(t))
    if cjk == 0:
        return "en"
    return "zh" if cjk >= 12 or cjk * 3 >= latin else "en"


def english_alias(skill: str) -> str:
    """给中文规范技能名找英文别名；本身就是英文的原样返回。

    词典结构：分类 -> {规范技能名: [别名...]}
    别名列表里通常混着中英文写法，取第一个「纯 ASCII」的别名；
    但规范名本身已是英文时（Python / Docker）必须原样返回 ——
    别名表里存的是小写形式，直接用会把专有名词写坏。
    """
    if _ASCII_ONLY_RE.match(skill):
        return skill
    for _category, items in SKILL_TAXONOMY.items():
        aliases = items.get(skill)
        if not aliases:
            continue
        for alias in aliases:
            if _ASCII_ONLY_RE.match(alias):
                return alias
        break
    return skill


def suggest_bullets(
    role_title: str,
    jd_text: str,
    existing_bullets: List[str],
    missing_keywords: List[str],
    lang: Optional[str] = None,
) -> List[str]:
    """给出一组离线句式模板。

    Args:
        role_title: 目标岗位名称（当前仅用于未来扩展）。
        jd_text: 岗位 JD 原文。
        existing_bullets: 简历里的原始描述（判断语言以它为准）。
        missing_keywords: 岗位要求但简历缺失的技能关键词。
        lang: 强制指定 "zh" / "en"；留空则自动跟随输入语言。
    """
    if lang is None:
        bullet_text = " ".join(b for b in existing_bullets if b)
        # 以「要改写的简历原文」为准：中文简历配英文 JD 时，模板也该是中文
        lang = detect_lang(bullet_text) if bullet_text.strip() else detect_lang(jd_text)

    patterns = _ZH_PATTERNS if lang == "zh" else _EN_PATTERNS
    tips: List[str] = []
    for idx, kw in enumerate(missing_keywords[:8]):
        name = kw if lang == "zh" else english_alias(kw)
        tips.append(patterns[idx % len(patterns)].format(kw=name))

    if not tips:
        tips.append(_ZH_FALLBACK if lang == "zh" else _EN_FALLBACK)
    return tips
