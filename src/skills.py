
"""技能词典与技能缺口分析。

设计目标：
1. 用一份可维护的中英文技能分类词典，把岗位 JD 与简历中的技能识别出来；
2. 对比二者得到「岗位要求 / 简历已具备 / 缺失」三组技能；
3. 供 UI、面试题生成、求职建议、报告复用。

注意：词典是启发式的，不追求 100% 召回，只要求「可解释」。
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# 技能分类词典： 分类 -> {规范技能名: [别名...]}
# 别名匹配规则：
#   - 纯英文/数字别名按「单词边界」匹配（避免 java 命中 javascript）
#   - 含 + # / . 或中文的别名按「子串」匹配
# ---------------------------------------------------------------------------
SKILL_TAXONOMY: Dict[str, Dict[str, List[str]]] = {
    "编程语言": {
        "Python": ["python"],
        "Java": ["java"],
        "C++": ["c++", "cpp", "c/c++"],
        "C": ["c语言"],
        "C#": ["c#", "csharp"],
        "JavaScript": ["javascript", "js"],
        "TypeScript": ["typescript", "ts"],
        "Go": ["golang", "go语言"],
        "Rust": ["rust"],
        "Kotlin": ["kotlin"],
        "PHP": ["php"],
        "MATLAB": ["matlab"],
        "Shell": ["shell", "bash"],
        "SQL": ["sql"],
    },
    "前端": {
        "React": ["react", "react.js", "reactjs"],
        "Vue": ["vue", "vue.js", "vue3"],
        "Angular": ["angular"],
        "Next.js": ["next.js", "nextjs"],
        "HTML": ["html", "html5"],
        "CSS": ["css", "css3"],
        "Webpack": ["webpack"],
        "小程序": ["小程序", "微信小程序"],
    },
    "后端与框架": {
        "Spring": ["spring", "spring boot", "springboot", "spring cloud", "springcloud"],
        "Django": ["django"],
        "Flask": ["flask"],
        "FastAPI": ["fastapi"],
        "Node.js": ["node.js", "nodejs"],
        "Express": ["express"],
        "MyBatis": ["mybatis"],
        "Hibernate": ["hibernate"],
        "RESTful API": ["rest", "restful", "rest api"],
        "微服务": ["微服务", "microservice", "microservices"],
        "Nacos": ["nacos"],
        "消息队列": ["kafka", "rabbitmq", "rocketmq", "消息队列"],
        "缓存": ["redis", "缓存"],
        "并发编程": ["并发", "多线程", "multithreading", "concurrency"],
    },
    "AI / 数据": {
        "机器学习": ["machine learning", "机器学习"],
        "深度学习": ["deep learning", "深度学习"],
        "NLP": ["nlp", "自然语言处理"],
        "计算机视觉": ["计算机视觉", "computer vision", "opencv"],
        "LLM": ["llm", "大模型", "大语言模型", "gpt", "chatgpt"],
        "PyTorch": ["pytorch"],
        "TensorFlow": ["tensorflow"],
        "Transformers": ["transformers", "sentence-transformers", "huggingface"],
        "LangChain": ["langchain"],
        "RAG": ["rag", "检索增强"],
        "Prompt 工程": ["prompt", "提示词"],
        "数据分析": ["pandas", "numpy", "数据分析", "data analysis"],
        "爬虫": ["爬虫", "scrapy", "crawler"],
        "向量检索": ["embedding", "向量", "faiss", "vector"],
    },
    "数据库": {
        "MySQL": ["mysql"],
        "PostgreSQL": ["postgresql", "postgres"],
        "Oracle": ["oracle"],
        "MongoDB": ["mongodb"],
        "SQLite": ["sqlite"],
        "Elasticsearch": ["elasticsearch", "elastic search"],
        "数据库设计": ["数据库设计", "范式", "索引优化"],
    },
    "云与运维": {
        "AWS": ["aws", "ec2", "s3", "lambda"],
        "GCP": ["gcp", "google cloud"],
        "Azure": ["azure"],
        "Docker": ["docker"],
        "Kubernetes": ["kubernetes", "k8s"],
        "CI/CD": ["ci/cd", "cicd", "持续集成", "持续交付"],
        "Jenkins": ["jenkins"],
        "Linux": ["linux", "ubuntu", "centos"],
        "Git": ["git", "github", "gitlab"],
        "Nginx": ["nginx"],
    },
    "嵌入式与硬件": {
        "嵌入式": ["嵌入式", "embedded"],
        "单片机": ["单片机", "stm32", "mcu", "51单片机"],
        "RTOS": ["rtos", "freertos"],
        "ISP": ["isp", "图像信号处理"],
        "摄像头": ["摄像头", "camera", "camera sensor"],
        "图像处理": ["图像处理", "image processing"],
        "驱动开发": ["驱动开发", "driver"],
        "通信协议": ["uart", "i2c", "spi", "can总线", "mqtt", "tcp/ip"],
    },
    "测试与工具": {
        "单元测试": ["unit test", "单元测试", "pytest", "junit"],
        "Postman": ["postman"],
        "Selenium": ["selenium"],
        "性能优化": ["性能优化", "performance tuning"],
    },
    "软技能": {
        "沟通表达": ["communication", "沟通"],
        "团队协作": ["teamwork", "团队协作", "跨部门"],
        "项目管理": ["项目管理", "project management"],
        "敏捷开发": ["agile", "scrum", "敏捷"],
        "英文文档": ["english", "英语"],
    },
}


def _alias_pattern(alias: str) -> str:
    """把别名编译成一个大小写不敏感的正则片段。"""
    escaped = re.escape(alias)
    if re.fullmatch(r"[A-Za-z0-9 ]+", alias):
        # 纯英文/数字：要求前后不是字母数字，避免 java 命中 javascript
        return r"(?<![A-Za-z0-9])" + escaped + r"(?![A-Za-z0-9])"
    return escaped


# 预编译所有别名正则，避免每次重复编译
_COMPILED: List[Tuple[str, str, re.Pattern]] = [
    (category, canonical, re.compile(_alias_pattern(alias), re.I))
    for category, skills in SKILL_TAXONOMY.items()
    for canonical, aliases in skills.items()
    for alias in aliases
]


def find_skills(text: str) -> Dict[str, List[str]]:
    """从文本中识别技能，返回 {分类: [规范技能名...]}（保序、去重）。"""
    if not text:
        return {}
    result: Dict[str, List[str]] = {}
    for category, canonical, pattern in _COMPILED:
        if pattern.search(text):
            bucket = result.setdefault(category, [])
            if canonical not in bucket:
                bucket.append(canonical)
    return result


def flat_skills(skill_map: Dict[str, List[str]]) -> List[str]:
    """把 {分类: [技能]} 拍平成一个列表。"""
    out: List[str] = []
    for items in skill_map.values():
        for s in items:
            if s not in out:
                out.append(s)
    return out


def skill_gap(jd_text: str, resume_text: str) -> Dict[str, object]:
    """对比 JD 与简历，给出技能缺口。

    返回:
        {
          "required": {分类: [技能]},   # 岗位要求中识别到的技能
          "owned":    {分类: [技能]},   # 简历中已具备的技能
          "missing":  {分类: [技能]},   # 岗位要求但简历缺失
          "coverage": float,            # 技能覆盖率 0~1
          "required_list": [技能],
          "owned_list": [技能],
          "missing_list": [技能],
        }
    """
    jd_skills = find_skills(jd_text)
    resume_skills = find_skills(resume_text)

    owned_flat = set(flat_skills(resume_skills))

    required = jd_skills
    missing: Dict[str, List[str]] = {}
    for category, items in required.items():
        for s in items:
            if s not in owned_flat:
                missing.setdefault(category, []).append(s)

    required_list = flat_skills(required)
    missing_list = flat_skills(missing)
    owned_list = [s for s in required_list if s not in set(missing_list)]  # 岗位相关且已具备

    coverage = (len(required_list) - len(missing_list)) / len(required_list) if required_list else 0.0

    return {
        "required": required,
        "owned": resume_skills,
        "missing": missing,
        "coverage": round(coverage, 4),
        "required_list": required_list,
        "owned_list": owned_list,
        "missing_list": missing_list,
    }
