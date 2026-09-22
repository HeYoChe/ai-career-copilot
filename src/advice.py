
"""AI 求职建议：把分析结果翻译成「能照着做」的行动项。

基础模式完全离线，靠词典 + 模板 + ATS 结果拼装；
配置了 API Key 则交给 LLM 生成更贴合的建议。
"""

from __future__ import annotations

from typing import Dict, List

from .llm import LLMError, chat

# ATS 检查项 -> 具体修改动作
SECTION_ACTION = {
    "文件名": "把简历文件名改成 `姓名-岗位-简历.pdf` 这种无空格形式，部分 ATS 对空格不友好。",
    "联系方式": "在简历抬头补一个常用邮箱（避免纯数字前缀的邮箱）。",
    "个人链接": "加上 GitHub 或 LinkedIn 链接。技术岗如果项目都开源在 GitHub，这个链接比 LinkedIn 更有说服力。",
    "篇幅": "内容超篇幅了，删掉与目标岗位无关的经历，保留 2~3 个最能体现岗位技能的项目。",
    "教育背景": "补充教育背景：学校、专业、起止时间、GPA 或排名。",
    "专业技能": "补充「专业技能」板块，把 JD 里的关键词按真实掌握程度分层列出来。",
    "项目经历": "补充「项目经历」，每个项目写清楚：做了什么、用了什么技术、产生了什么结果。",
    "实习/工作经历": "补充实习/工作经历；如果没有，用课程项目或竞赛经历替代也可以。",
}


def build_strengths(gap: Dict[str, object], semantic_score: float, coverage: float) -> List[str]:
    """提炼候选人的优势（离线规则）。"""
    strengths: List[str] = []
    matched: List[str] = list(gap.get("owned_list", []))  # type: ignore[arg-type]
    required: List[str] = list(gap.get("required_list", []))  # type: ignore[arg-type]

    if matched:
        strengths.append(
            f"与岗位直接对口的技能有 {len(matched)} 项：{'、'.join(matched[:8])}，"
            "这些是面试中最应该主动展开讲的点。"
        )
    if coverage >= 0.6:
        strengths.append(f"岗位要求技能的覆盖率达到 {int(coverage * 100)}%，属于「可以投」的水平。")
    elif coverage >= 0.35:
        strengths.append(
            f"岗位要求技能覆盖率 {int(coverage * 100)}%，基础对得上，但需要用项目细节补足说服力。"
        )

    # 简历里超出岗位要求的额外技能（技术面广）
    extra = [s for s in gap.get("owned", {}).values()]  # type: ignore[union-attr]
    extra_flat = [s for group in extra for s in group]
    bonus = [s for s in extra_flat if s not in set(required)]
    if bonus:
        strengths.append(
            f"简历里还有 {len(bonus)} 项岗位未强制要求的技术（{'、'.join(bonus[:6])}），"
            "可以说明学习能力和技术广度。"
        )

    if semantic_score >= 0.5:
        strengths.append("简历整体表述与岗位描述的语义接近度较高，说明经历方向匹配。")

    if not strengths:
        strengths.append("目前简历与岗位的直接重合点不多，建议先按下面的缺口清单补齐关键词再投递。")
    return strengths


def build_resume_tips(gap: Dict[str, object], ats_issues: List) -> List[str]:
    """简历修改建议（离线规则）。"""
    tips: List[str] = []

    missing: List[str] = list(gap.get("missing_list", []))  # type: ignore[arg-type]
    if missing:
        tips.append(
            "**优先补关键词**：JD 要求但简历未出现的有 " + "、".join(missing[:8]) + "。"
        )
        for skill in missing[:4]:
            tips.append(
                f"- `{skill}`：如果你确实用过，就在项目描述里补一句「使用 {skill} 完成 XXX」；"
                f"如果没用过，不要硬写，改成「了解 {skill}，正在通过 XXX 练习」放在技能栏末尾。"
            )

    # 结构化表达建议
    tips.append("**用结果说话**：每条经历尽量写成「动词 + 做了什么 + 用了什么技术 + 带来了什么结果（数字）」。")
    tips.append("**动词开头**：把「负责」「参与」换成「设计」「实现」「优化」「重构」「部署」。")

    if not ats_issues:
        tips.append("ATS 检查没有发现明显问题，保持一页、纯文本可解析即可。")
    else:
        tips.append("**按 ATS 检查逐条修**：")
        for issue in ats_issues:
            if isinstance(issue, (list, tuple)) and len(issue) == 2:
                key, _msg = issue[0], issue[1]
                tips.append(f"- {SECTION_ACTION.get(str(key), str(key) + '：按检查提示修正。')}")

    tips.append("**投递前自查**：把 JD 复制出来，逐条对照简历，确认每个硬性要求都能在简历里找到对应表述。")
    return tips


def build_interview_focus(gap: Dict[str, object]) -> List[str]:
    """面试准备重点（离线规则）。"""
    focus: List[str] = []
    missing: List[str] = list(gap.get("missing_list", []))  # type: ignore[arg-type]
    matched: List[str] = list(gap.get("owned_list", []))  # type: ignore[arg-type]

    for skill in missing[:3]:
        focus.append(
            f"`{skill}` 一定会被问到：准备好「我目前了解到什么程度 + 打算怎么补」的诚实回答，"
            "比硬编造经历安全得多。"
        )
    for skill in matched[:3]:
        focus.append(f"`{skill}` 是你简历上的加分项，准备好一个能展开讲 3 分钟的具体项目案例。")
    focus.append("每个项目都准备一个「最大难点 + 怎么定位 + 怎么解决 + 结果」的完整故事。")
    focus.append("准备 2 个反问面试官的问题（团队技术栈、新人培养方式等）。")
    return focus


def render_advice_markdown(
    strengths: List[str],
    resume_tips: List[str],
    interview_focus: List[str],
    mode_label: str = "基础模式",
) -> str:
    lines = [f"> 建议生成模式：{mode_label}", ""]
    lines.append("### 你的优势")
    lines += [f"- {s}" if not s.startswith("-") else s for s in strengths]
    lines.append("")
    lines.append("### 简历修改建议")
    lines += [f"- {t}" if not t.startswith("-") else t for t in resume_tips]
    lines.append("")
    lines.append("### 面试准备重点")
    lines += [f"- {f}" if not f.startswith("-") else f for f in interview_focus]
    return "\n".join(lines)


_ADVICE_SYSTEM = (
    "你是资深求职顾问，服务对象是应届生/实习生。请基于给定的简历与岗位 JD，输出中文 Markdown 建议，"
    "包含三个小节：## 你的优势 / ## 简历修改建议 / ## 面试准备重点。\n"
    "硬性要求：只能基于简历中真实存在的信息给建议，绝不能编造项目、公司、技术或数据指标；"
    "每条建议要具体到「改哪一句、怎么改」。"
)


def produce_llm_advice(
    resume_text: str,
    jd_text: str,
    gap: Dict[str, object],
    ats_issues: List,
    config: dict,
) -> str:
    """LLM 版求职建议，失败抛 LLMError。"""
    missing = "、".join(list(gap.get("missing_list", []))[:8]) or "无"  # type: ignore[arg-type]
    matched = "、".join(list(gap.get("owned_list", []))[:10]) or "无"  # type: ignore[arg-type]
    ats_text = "；".join(
        f"{i[0]}: {i[1]}" for i in ats_issues if isinstance(i, (list, tuple)) and len(i) == 2
    ) or "无"

    user = (
        f"【目标岗位 JD】\n{jd_text[:3000]}\n\n"
        f"【候选人简历】\n{resume_text[:4000]}\n\n"
        f"【系统分析】岗位要求且已具备：{matched}；缺失：{missing}；ATS 问题：{ats_text}\n\n"
        "请输出优化建议。"
    )
    return chat(
        [{"role": "system", "content": _ADVICE_SYSTEM}, {"role": "user", "content": user}],
        config,
        temperature=0.4,
        max_tokens=1600,
    )


# ---------------------------------------------------------------------------
# 简历 bullet 优化（LLM 模式；基础模式见 rewrite.py）
# ---------------------------------------------------------------------------
_BULLET_SYSTEM = (
    "你是简历优化专家。请优化给定的简历描述，使其更贴合目标岗位 JD。\n"
    "硬性要求：\n"
    "1. 只优化「表达方式」。原文里没有的技术、工具、平台、框架、职责、公司、时间、数字指标，\n"
    "   一律不得出现 —— 改写后的每一句话都要能在原文里找到依据；\n"
    "2. 不得为了让简历「更贴合 JD」而添加候选人没有的技能。JD 里有、但原文没提到的能力，\n"
    "   只能写进「### 还需要你补充的信息」向用户提问，绝不能写进「### 优化后」的描述里；\n"
    "3. 原文已有的量化数据一律原样保留；只有当一段描述完全没有任何数字时，\n"
    "   才用 `[请填写具体数据]` 提示用户补充，不要自己编数字；\n"
    "4. 输出 Markdown，包含：### 优化后 / ### 修改说明 / ### 还需要你补充的信息；\n"
    "5. 输出前自检：把「### 优化后」里新出现的每个技术名词、工具名和数字逐个回原文核对，\n"
    "   凡是原文中找不到的，删掉或改成向用户提问。"
)


def produce_llm_bullet_rewrite(
    bullet: str,
    jd_text: str,
    missing: List[str],
    config: dict,
) -> str:
    user = (
        f"【目标岗位 JD】\n{jd_text[:2000]}\n\n"
        f"【岗位要求、但候选人简历中缺失的关键词】{'、'.join(missing[:8]) or '无'}\n"
        "（⚠️ 以上关键词代表候选人**目前不具备**的能力，只用来帮你判断已有经历里哪些值得强调。\n"
        "  严禁把它们写进「### 优化后」的描述，否则等于替候选人编造经历；\n"
        "  如果它们对岗位确实重要，请放进「### 还需要你补充的信息」向用户提问。）\n\n"
        f"【需要优化的简历原文】\n{bullet[:1500]}\n\n"
        "请在不虚构事实的前提下优化这段描述。"
    )
    return chat(
        [{"role": "system", "content": _BULLET_SYSTEM}, {"role": "user", "content": user}],
        config,
        temperature=0.4,
        max_tokens=1200,
    )
