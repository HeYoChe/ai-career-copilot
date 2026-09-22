
"""ATS 与简历卫生检查（基础规则版）。

检查项：文件名、联系方式、个人链接、篇幅、必备章节。
注意：这些是启发式规则，不同 ATS 实现差异很大，只作为「明显问题」的提示。
"""

from __future__ import annotations

import re

# 章节探测：中英文都支持
SECTION_PATTERNS = {
    "教育背景": r"(education|university|college|b\.?s\.?|bachelor|master|教育|大学|学院|学历)",
    "专业技能": r"(skills?|technical skills|技能|技术栈|掌握)",
    "项目经历": r"(projects?|项目)",
    "实习/工作经历": r"(experience|internship|employment|实习|工作经历|经历)",
}


def basic_ats_checks(resume_text: str, filename: str = "resume.pdf"):
    """返回 [(检查项, 建议)] 列表；没有问题则返回空列表。"""
    checks = []

    # 1) 文件名规范
    if re.search(r"\s", filename):
        checks.append(("文件名", "文件名里有空格，建议改成 `姓名-岗位-简历.pdf` 这种无空格形式。"))

    # 2) 联系方式（naive 检查）
    if not re.search(r"\b[\w\.-]+@[\w\.-]+\.[A-Za-z]{2,}\b", resume_text):
        checks.append(("联系方式", "没检测到邮箱，建议在抬头补一个常用邮箱。"))

    # 3) 个人链接：GitHub 或 LinkedIn 至少有一个
    if not re.search(r"(linkedin\.com/in/|github\.com/)", resume_text, re.I):
        checks.append(("个人链接", "没检测到 GitHub / LinkedIn 链接，技术岗建议加上。"))

    # 4) 篇幅（粗略）
    words = len(resume_text.split())
    if words > 900:
        checks.append(("篇幅", "文字量偏多，实习/校招简历建议压缩到 1 页，只留与岗位相关的经历。"))

    # 5) 必备章节
    for name, pattern in SECTION_PATTERNS.items():
        if re.search(pattern, resume_text, re.I) is None:
            checks.append((name, f"没有检测到「{name}」相关内容，建议补上。"))

    return checks
