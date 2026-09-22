
"""AI 模拟面试：根据「简历 + 岗位 JD」生成个性化面试问题。

两种模式：
- 基础模式（无需 API Key）：基于规则 + 模板，从简历中抽取项目名，
  结合 JD 技能要求与技能缺口，拼装出结构化的问题清单；
- LLM 模式（配置 API Key 后）：交给大模型生成更自然、更贴合的问题，
  失败时自动回退到基础模式。
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from .llm import LLMError, chat

# ---------------------------------------------------------------------------
# 常见技能的高频面试问题（基础模式的素材库）
# ---------------------------------------------------------------------------
SKILL_QUESTIONS: Dict[str, List[str]] = {
    "Python": [
        "你在 Python 项目里如何组织代码结构和依赖管理（虚拟环境、requirements 等）？",
        "Python 的装饰器和生成器你实际在什么场景下用过？请举例说明。",
    ],
    "Java": [
        "你能解释一下 Java 的内存模型和垃圾回收机制吗？你遇到过 GC 问题吗？",
        "Java 中 HashMap 的底层实现是怎样的？为什么线程不安全？",
    ],
    "C++": [
        "C++ 中指针和引用有什么区别？你在项目中如何避免内存泄漏？",
        "你了解 C++ 的 RAII 吗？它在资源管理上解决了什么问题？",
    ],
    "C": [
        "C 语言里你如何管理动态内存？遇到段错误一般怎么定位？",
        "volatile、static、const 这几个关键字分别是什么含义？",
    ],
    "JavaScript": [
        "请说明 JavaScript 的事件循环（Event Loop）和微任务/宏任务执行顺序。",
        "闭包是什么？你在实际项目里用它解决过什么问题？",
    ],
    "TypeScript": [
        "TypeScript 的 interface 和 type 有什么区别？你在项目里怎么选？",
        "泛型在你写过的代码里怎么用的？能举一个例子吗？",
    ],
    "React": [
        "React 的 useEffect 依赖数组为空、有依赖、不写依赖三种情况分别意味着什么？",
        "你在项目里怎么做组件状态管理？为什么这样选？",
    ],
    "Vue": [
        "Vue 的响应式原理是什么？Vue2 和 Vue3 有什么区别？",
        "组件之间通信你用过哪些方式？分别在什么场景下使用？",
    ],
    "Spring": [
        "Spring 的 IoC 和 AOP 分别解决了什么问题？你在项目里怎么用的？",
        "Spring Boot 的自动装配原理是什么？starter 起了什么作用？",
    ],
    "微服务": [
        "你们的微服务是怎么拆分的？服务之间如何通信和保证一致性？",
        "服务注册与发现、配置中心你用的什么方案？为什么选它？",
    ],
    "MySQL": [
        "一条 SQL 很慢，你会怎么排查和优化？索引在什么情况下会失效？",
        "事务的隔离级别有哪些？你们项目里用的哪一级，为什么？",
    ],
    "Redis": [
        "Redis 的常用数据结构有哪些？你在项目里用它解决什么问题？",
        "缓存穿透、缓存击穿、缓存雪崩分别是什么？如何应对？",
    ],
    "Oracle": [
        "Oracle 和 MySQL 在使用上有哪些你感受到的差异？",
        "PL/SQL 存储过程你在什么场景下会使用？",
    ],
    "Docker": [
        "镜像和容器的区别是什么？你怎么写一个体积更小的镜像？",
        "你平时用 Docker Compose 吗？怎么管理多容器依赖关系？",
    ],
    "Git": [
        "团队协作时你们用的什么分支策略？发生冲突你怎么处理？",
        "rebase 和 merge 的区别是什么？什么情况下用哪个？",
    ],
    "Linux": [
        "排查线上问题时你最常用哪些命令？请描述一次完整的排查过程。",
        "Linux 的进程、线程和文件权限你能简单说明一下吗？",
    ],
    "机器学习": [
        "你怎么判断一个模型是过拟合还是欠拟合？分别怎么处理？",
        "你做过特征工程吗？举一个你认为最有效的特征处理。",
    ],
    "深度学习": [
        "你训练模型时如何选择损失函数和优化器？为什么？",
        "训练不收敛你会从哪些方面排查？",
    ],
    "NLP": [
        "文本预处理你一般会做哪些步骤？中文和英文处理有什么区别？",
        "你了解词向量和句向量的区别吗？Embedding 在这里的作用是什么？",
    ],
    "LLM": [
        "你怎么控制大模型输出的稳定性和格式？用过哪些手段？",
        "如果大模型编造了不存在的内容，你会怎么降低这种风险？",
    ],
    "PyTorch": [
        "PyTorch 里 Dataset 和 DataLoader 你是怎么用的？",
        "训练时显存不够，你会怎么优化？",
    ],
    "嵌入式": [
        "你在嵌入式项目里做过哪些底层调试？用了什么工具？",
        "中断和轮询的区别是什么？实际项目中你怎么选？",
    ],
    "单片机": [
        "你用的哪款 MCU？资源受限时你怎么权衡性能和内存？",
        "I2C、SPI、UART 三种通信方式有什么区别？",
    ],
    "ISP": [
        "你为什么关注 ISP 方向？对这个链路的技术点了解多少？",
        "ISP 中的 3A 算法（AE/AWB/AF）解决的是什么问题？",
    ],
    "摄像头": [
        "你接触过摄像头模组的调试吗？遇到过什么图像质量问题？",
        "如果图像偏暗或噪声很大，你会从哪些环节排查原因？",
    ],
    "计算机视觉": [
        "传统图像处理和深度学习在视觉任务上你怎么选？",
        "你做过的视觉任务里，数据量不足时你怎么处理？",
    ],
    "爬虫": [
        "你写爬虫时怎么处理反爬和请求频率问题？",
        "爬下来的数据你怎么清洗和存储？",
    ],
    "单元测试": [
        "你的项目里测试覆盖率大概多少？怎么保证关键逻辑被测到？",
        "一个依赖数据库的函数，你会怎么做单元测试？",
    ],
}

GENERIC_SKILL_QUESTIONS = [
    "你在 {skill} 方面做过哪些具体实践？请结合一个项目说明。",
    "{skill} 中你踩过印象最深的坑是什么？最后怎么解决的？",
]

PROJECT_QUESTION_TEMPLATES = [
    "请介绍一下「{project}」，你的角色是什么？具体负责哪一部分？",
    "「{project}」里你遇到的最大技术挑战是什么？你是如何定位并解决的？",
    "「{project}」的技术选型是怎么定的？如果重做一次你会换掉什么？",
    "「{project}」上线（或交付）后，你怎么验证它的效果？",
]

MISSING_SKILL_QUESTIONS = [
    "岗位要求 {skill}，但你的简历中体现得不多。能说说你对 {skill} 的了解程度吗？",
    "如果入职后需要你尽快上手 {skill}，你会怎么安排学习节奏？",
]

MATCH_QUESTIONS = [
    "你为什么投递这个岗位？你觉得自己的经历和它最匹配的地方是什么？",
    "你的技能栈和岗位要求相比，最大的短板在哪里？你准备怎么补？",
]

BEHAVIOR_QUESTIONS = [
    "讲一次你和团队意见不一致的经历，你最后是怎么推进的？",
    "说一个你自学新技术的例子：为什么学、怎么学、结果如何？",
    "你遇到过 deadline 很紧的任务吗？你是怎么安排优先级的？",
]


# ---------------------------------------------------------------------------
# 简历项目名抽取（基础模式用）
# ---------------------------------------------------------------------------
_SECTION_HEADS = {
    "projects", "project", "personal projects", "projects & awards", "selected projects",
    "项目", "项目经历", "项目经验", "主要项目",
}
_KNOWN_HEADS = {
    "education", "skills", "technical skills", "experience", "work experience",
    "internship", "awards", "honors", "certifications", "summary", "profile",
    "教育背景", "教育经历", "专业技能", "技能", "实习经历", "工作经历", "荣誉", "证书", "自我评价",
}
# 兜底用的关键词（英文按单词边界匹配，避免 Engineering 命中 engine）
_PROJECT_KEYWORDS_CN = ("项目", "系统", "平台", "网站", "小程序", "引擎", "机器人", "助手")
_PROJECT_KEYWORDS_EN = (
    "project", "system", "platform", "website", "engine", "app",
    "dashboard", "tool", "server", "analyzer", "copilot", "chatroom",
)
_EN_PROJECT_RE = re.compile(
    r"(?<![a-z])(" + "|".join(_PROJECT_KEYWORDS_EN) + r")(?![a-z])", re.I
)
_CONTACT_RE = re.compile(r"@|\+?\d[\d\s\-]{6,}|linkedin\.com|github\.com")


def _is_heading(line: str) -> bool:
    """判断一行是否像「章节标题」。"""
    stripped = line.strip().strip(":：")
    low = stripped.lower()
    if low in _KNOWN_HEADS or low in _SECTION_HEADS:
        return True
    return 3 <= len(stripped) <= 40 and stripped.isupper()


def _is_project_like(line: str, via_section: bool) -> bool:
    """判断一行是否像项目名。"""
    stripped = line.strip()
    if not (3 <= len(stripped) <= 60):
        return False
    if _CONTACT_RE.search(stripped):
        return False
    if stripped[0] in "-–—•*●":  # 条目型描述，不是标题
        return False
    if via_section:
        return True
    if any(k in stripped for k in _PROJECT_KEYWORDS_CN):
        return True
    return bool(_EN_PROJECT_RE.search(stripped))


def extract_projects(resume_raw: str, limit: int = 4) -> List[str]:
    """从简历原始文本（保留换行）中抽取项目名。

    优先用结构信息：定位「PROJECTS / 项目经历」标题，取其后到下一个章节之前的短行；
    如果没有这样的章节，再退回关键词启发式。
    """
    if not resume_raw:
        return []

    lines = [re.sub(r"[ \t\u3000]+", " ", ln).strip() for ln in resume_raw.splitlines()]
    lines = [ln for ln in lines if ln]

    # --- 策略 1：按章节结构抽取（更准） ---
    in_projects = False
    from_section: List[str] = []
    for line in lines:
        norm = line.strip().strip(":：").lower()
        if norm in _SECTION_HEADS or norm.startswith("项目"):
            in_projects = True
            continue
        if not in_projects:
            continue
        if _is_heading(line):
            break  # 进入下一个章节
        if _is_project_like(line, via_section=True) and line not in from_section:
            from_section.append(line)
        if len(from_section) >= limit:
            break
    if from_section:
        return from_section[:limit]

    # --- 策略 2：关键词兜底 ---
    candidates: List[str] = []
    for line in lines:
        if _is_heading(line):
            continue
        if not _is_project_like(line, via_section=False):
            continue
        if line not in candidates:
            candidates.append(line)
    return candidates[:limit]


# ---------------------------------------------------------------------------
# 基础模式：规则生成面试题
# ---------------------------------------------------------------------------
CATEGORY_ORDER = ["项目深挖", "技术基础", "技能缺口", "岗位匹配", "行为面试"]


def generate_questions(
    resume_raw: str,
    resume_text: str,
    jd_text: str,
    gap: Dict[str, object],
    max_questions: int = 10,
) -> List[Dict[str, str]]:
    """规则模式生成面试题，返回 [{category, question, basis}]。

    先按类别分别装桶，再「轮流取一道」，保证题目数量受控时各类别都不会被整类裁掉。
    """
    buckets: Dict[str, List[Dict[str, str]]] = {c: [] for c in CATEGORY_ORDER}
    seen: set = set()

    def add(category: str, question: str, basis: str) -> None:
        q = question.strip()
        if not q or q in seen:
            return
        seen.add(q)
        buckets[category].append({"category": category, "question": q, "basis": basis})

    # 1) 项目深挖：广度优先——先保证每个项目都被问到，再回头深挖第一个项目
    projects = extract_projects(resume_raw)
    for project in projects[:3]:
        add("项目深挖", PROJECT_QUESTION_TEMPLATES[0].format(project=project), f"来自简历项目：{project}")
    for project in projects[:1]:
        for tpl in PROJECT_QUESTION_TEMPLATES[1:3]:
            add("项目深挖", tpl.format(project=project), f"来自简历项目：{project}")

    # 2) 岗位要求且简历已具备 → 技术深度题
    required_list: List[str] = list(gap.get("required_list", []))  # type: ignore[arg-type]
    for skill in required_list[:5]:
        bank = SKILL_QUESTIONS.get(skill)
        if bank:
            add("技术基础", bank[0], f"岗位要求 + 简历具备：{skill}")
        else:
            add("技术基础", GENERIC_SKILL_QUESTIONS[0].format(skill=skill), f"岗位要求 + 简历具备：{skill}")

    # 3) 技能缺口 → 反差解释题
    for skill in list(gap.get("missing_list", []))[:3]:  # type: ignore[arg-type]
        add("技能缺口", MISSING_SKILL_QUESTIONS[0].format(skill=skill), f"岗位要求但简历缺失：{skill}")

    # 4) 岗位匹配 / 5) 行为面试
    for q in MATCH_QUESTIONS:
        add("岗位匹配", q, "通用岗位匹配问题")
    for q in BEHAVIOR_QUESTIONS:
        add("行为面试", q, "通用行为面试问题")

    # 轮流取题：先保证每个类别至少一道，再按轮次补齐
    result: List[Dict[str, str]] = []
    round_idx = 0
    while len(result) < max_questions:
        added_this_round = False
        for category in CATEGORY_ORDER:
            bucket = buckets[category]
            if round_idx < len(bucket):
                result.append(bucket[round_idx])
                added_this_round = True
                if len(result) >= max_questions:
                    break
        if not added_this_round:
            break
        round_idx += 1
    return result


def render_questions_markdown(questions: List[Dict[str, str]]) -> str:
    """把问题列表渲染成 Markdown（用于页面展示和报告导出）。"""
    lines: List[str] = []
    current = None
    index = 0
    for item in questions:
        if item["category"] != current:
            current = item["category"]
            lines.append(f"\n**{current}**\n")
        index += 1
        lines.append(f"{index}. {item['question']}")
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# LLM 模式
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "你是一位有十年经验的技术面试官。你要根据候选人的简历和目标岗位 JD，"
    "生成有针对性的面试问题。要求：\n"
    "1. 必须结合简历里真实出现过的项目、技术栈和 JD 里的要求，不要泛泛而问；\n"
    "2. 不要捏造简历中不存在的经历；\n"
    "3. 难度贴合校招/实习到初级岗位；\n"
    "4. 输出严格的 JSON 数组，不要输出多余解释。"
)


def produce_llm_questions(
    resume_text: str,
    jd_text: str,
    gap: Dict[str, object],
    config: dict,
    max_questions: int = 10,
) -> List[Dict[str, str]]:
    """用 LLM 生成面试题；解析失败时抛 LLMError 由调用方回退。"""
    missing = "、".join(list(gap.get("missing_list", []))[:8]) or "无"  # type: ignore[arg-type]
    matched = "、".join(list(gap.get("owned_list", []))[:10]) or "无"  # type: ignore[arg-type]

    user_prompt = (
        f"【目标岗位 JD】\n{jd_text[:3000]}\n\n"
        f"【候选人简历】\n{resume_text[:4000]}\n\n"
        f"【系统分析出的岗位要求技能】{matched}\n"
        f"【系统分析出的技能缺口】{missing}\n\n"
        f"请生成 {max_questions} 个面试问题，覆盖以下类别："
        "项目深挖、技术基础、技能缺口、岗位匹配、行为面试。\n"
        '输出格式（严格 JSON 数组，不要 markdown 代码块）：\n'
        '[{"category": "项目深挖", "question": "..."}]'
    )

    raw = chat(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        config,
        temperature=0.5,
        max_tokens=1600,
    )

    items = _parse_json_questions(raw)
    if not items:
        raise LLMError("模型返回内容无法解析为面试题列表。")
    return items[:max_questions]


def _parse_json_questions(raw: str) -> List[Dict[str, str]]:
    """容错解析：直接 JSON → 去掉代码块 → 正则抓字段 → 编号列表兜底。"""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()

    def _from_data(data) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("question"):
                    out.append(
                        {
                            "category": str(item.get("category", "面试问题")),
                            "question": str(item["question"]).strip(),
                            "basis": "由 AI 生成",
                        }
                    )
                elif isinstance(item, str) and item.strip():
                    out.append({"category": "面试问题", "question": item.strip(), "basis": "由 AI 生成"})
        return out

    try:
        items = _from_data(json.loads(text))
        if items:
            return items
    except Exception:
        pass

    match = re.search(r"\[.*\]", text, re.S)
    if match:
        try:
            items = _from_data(json.loads(match.group(0)))
            if items:
                return items
        except Exception:
            pass

    # 兜底：按编号行解析
    items = []
    for line in text.splitlines():
        m = re.match(r"^\s*(?:\d+[\.、)]|[-*])\s*(.+)$", line)
        if m and len(m.group(1).strip()) > 6:
            items.append({"category": "面试问题", "question": m.group(1).strip(), "basis": "由 AI 生成"})
    return items


# ---------------------------------------------------------------------------
# P2：面试回答点评（可选，需要 API Key）
# ---------------------------------------------------------------------------
def review_answer(question: str, answer: str, jd_text: str, config: dict) -> str:
    """对用户的回答给出点评。无 Key 或调用失败时抛 LLMError。"""
    if not answer.strip():
        raise LLMError("请先填写你的回答。")

    system = (
        "你是一位严格但友好的技术面试官。请点评候选人的回答，"
        "用中文输出 Markdown，包含四个小节：优点 / 存在的问题 / 改进建议 / 参考回答要点。"
        "不要编造候选人没有提到的经历。"
    )
    user = (
        f"【岗位 JD】\n{jd_text[:1500]}\n\n"
        f"【面试问题】{question}\n\n"
        f"【候选人回答】{answer[:2500]}\n\n"
        "请给出点评。"
    )
    return chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        config,
        temperature=0.3,
        max_tokens=1200,
    )
