
"""综合评分：把「语义匹配」和「技能覆盖」合成一个可解释的分数。

为什么不用单一余弦相似度？
- 纯向量相似度对中英文、对长短文本都敏感，单看一个数字容易被误读；
- 拆成「语义 60% + 技能覆盖 40%」后，每一部分都能在面试里讲清楚；
- 当本地 embedding 不可用时，还能降级为纯词面重合度，保证应用不崩。
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .match import tokenize_simple

SEMANTIC_WEIGHT = 0.6
COVERAGE_WEIGHT = 0.4


def combine_score(semantic: float, coverage: float, has_semantic: bool = True) -> float:
    """合成 0~1 的综合分。没有语义分时退化为覆盖率。"""
    if not has_semantic:
        return round(max(0.0, min(coverage, 1.0)), 4)
    score = SEMANTIC_WEIGHT * semantic + COVERAGE_WEIGHT * coverage
    return round(max(0.0, min(score, 1.0)), 4)


def lexical_overlap(jd_text: str, resume_text: str) -> float:
    """词面重合度（Jaccard 变体）：embedding 不可用时的降级方案。"""
    jd_tokens = set(tokenize_simple(jd_text))
    rs_tokens = set(tokenize_simple(resume_text))
    if not jd_tokens:
        return 0.0
    return round(len(jd_tokens & rs_tokens) / len(jd_tokens), 4)


def score_label(score: float) -> Tuple[str, str]:
    """把分数翻译成人话，返回 (标签, 颜色提示)。"""
    if score >= 0.75:
        return "高度匹配，建议尽快投递", "normal"
    if score >= 0.55:
        return "基本匹配，优化关键词后可提升通过率", "normal"
    if score >= 0.35:
        return "部分匹配，需要针对岗位补简历", "off"
    return "匹配度偏低，建议换岗位或先补技能", "off"


def score_breakdown(semantic: float, coverage: float) -> Dict[str, float]:
    return {
        "semantic": round(float(semantic), 4),
        "coverage": round(float(coverage), 4),
        "overall": combine_score(semantic, coverage),
    }


def highlight_tokens(jd_text: str, resume_text: str, limit: int = 20) -> List[str]:
    """词面级别：JD 中出现、简历中没有的词（作为技能词典的补充）。"""
    jd_tokens = set(tokenize_simple(jd_text))
    rs_tokens = set(tokenize_simple(resume_text))
    stop = {
        "and", "the", "for", "with", "you", "are", "will", "our", "your", "from", "that", "have",
        "this", "into", "work", "team", "skills", "experience", "years", "per", "week", "job",
        "role", "requirements", "responsibilities", "preferred", "must", "about", "company",
        "ability", "strong", "excellent", "good", "plus", "etc", "other", "using",
    }
    missing = [
        w for w in jd_tokens
        if w not in rs_tokens and len(w) > 2 and w not in stop
        and "/" not in w          # python/javascript 这类斜杠串交给技能词典处理
        and not w.isdigit()
    ]
    missing.sort(key=lambda w: (-len(w), w))
    return missing[:limit]
