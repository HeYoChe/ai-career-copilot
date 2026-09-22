
"""报告生成：把各模块结果汇总成可下载的 Markdown 求职报告。"""

from __future__ import annotations

from typing import Dict, List, Optional

from .interview import render_questions_markdown


def build_full_report(
    semantic_score: float,
    coverage: float,
    overall_score: float,
    gap: Dict[str, object],
    ats_issues: List,
    questions: List[Dict[str, str]],
    advice_markdown: str,
    model_name: str,
    llm_mode: str,
) -> str:
    """生成综合求职报告（Markdown）。"""
    lines: List[str] = []
    lines.append("# AI Career Copilot 求职分析报告")
    lines.append("")
    lines.append("## 一、综合匹配度")
    lines.append("")
    lines.append("| 指标 | 数值 | 说明 |")
    lines.append("| --- | --- | --- |")
    lines.append(f"| 综合匹配度 | **{overall_score * 100:.1f} / 100** | 语义匹配 60% + 技能覆盖 40% |")
    lines.append(f"| 语义匹配度 | {semantic_score * 100:.1f} / 100 | 简历与 JD 的 embedding 余弦相似度 |")
    lines.append(f"| 技能覆盖率 | {coverage * 100:.1f}% | JD 要求的技能在简历中出现的比例 |")
    lines.append(f"| 向量模型 | `{model_name}` | 本地运行，无需联网 |")
    lines.append(f"| 建议生成模式 | {llm_mode} | — |")
    lines.append("")

    lines.append("## 二、技能盘点")
    lines.append("")
    missing = list(gap.get("missing_list", []))  # type: ignore[arg-type]
    owned = list(gap.get("owned_list", []))  # type: ignore[arg-type]
    lines.append(f"**岗位要求且简历已具备（{len(owned)} 项）**：" + ("、".join(owned) if owned else "无"))
    lines.append("")
    lines.append(f"**岗位要求但简历缺失（{len(missing)} 项）**：" + ("、".join(missing) if missing else "无"))
    lines.append("")

    required_map = gap.get("required", {}) or {}
    if isinstance(required_map, dict) and required_map:
        lines.append("### 岗位技能分类明细")
        lines.append("")
        lines.append("| 分类 | 要求技能 | 简历是否具备 |")
        lines.append("| --- | --- | --- |")
        for category, skills in required_map.items():  # type: ignore[union-attr]
            for skill in skills:
                mark = "✅" if skill in owned else "❌"
                lines.append(f"| {category} | {skill} | {mark} |")
        lines.append("")

    lines.append("## 三、ATS 与简历卫生检查")
    lines.append("")
    if ats_issues:
        for issue in ats_issues:
            if isinstance(issue, (list, tuple)) and len(issue) == 2:
                lines.append(f"- **{issue[0]}**：{issue[1]}")
            else:
                lines.append(f"- {issue}")
    else:
        lines.append("未发现明显问题。")
    lines.append("")

    lines.append("## 四、简历优化与求职建议")
    lines.append("")
    lines.append(advice_markdown.strip())
    lines.append("")

    lines.append("## 五、AI 模拟面试题")
    lines.append("")
    if questions:
        lines.append(render_questions_markdown(questions))
    else:
        lines.append("尚未生成面试题。")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "> 说明：本报告由 AI Career Copilot 自动生成。匹配度为启发式指标，"
        "关键词与建议仅作参考，请务必只保留真实经历。"
    )
    return "\n".join(lines)
