
"""AI Career Copilot · AI 智能求职助手

主流程：
    简历解析 → 语义匹配 → 技能缺口 → ATS 检查 → AI 模拟面试 → 简历优化 → 求职报告

设计原则：
- 没有 API Key 也必须完整可用（基础模式）；
- 配置 API Key 后自动升级为 AI 模式；
- 所有分析结果留在 session_state，切换标签页不丢失。
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import streamlit as st

# 项目根目录：用 __file__ 定位，不依赖启动时的工作目录。
# 这样无论是目录改名、还是从别处用绝对路径启动，样式表和示例数据都能找到。
BASE_DIR = Path(__file__).resolve().parent

from src.advice import (
    build_interview_focus,
    build_resume_tips,
    build_strengths,
    produce_llm_advice,
    produce_llm_bullet_rewrite,
    render_advice_markdown,
)
from src.ats import basic_ats_checks
from src.embed import DEFAULT_MODEL, MULTILINGUAL_MODEL, embed_single
from src.extract import clean_text, extract_bullets, normalize_lines, read_pdf
from src.interview import (
    generate_questions,
    produce_llm_questions,
    render_questions_markdown,
    review_answer,
)
from src.llm import LLMError, is_configured, resolve_config
from src.match import similarity
from src.report import build_full_report
from src.rewrite import suggest_bullets
from src.scoring import combine_score, highlight_tokens, lexical_overlap, score_label
from src.skills import skill_gap

APP_NAME = "AI Career Copilot"
APP_NAME_CN = "AI 智能求职助手"

# 向量模型说明（侧边栏逐条展示，两个模型都要讲清楚）
EMBED_MODEL_INFO = {
    DEFAULT_MODEL: {
        "label": DEFAULT_MODEL,
        "short": "all-MiniLM-L6-v2 · 轻量英文",
        "tag": "英文推荐 · 约 90MB",
        "desc": (
            "体积小、CPU 上毫秒级出结果，本地已缓存，断网也能跑。"
            "<br>英文简历 + 英文 JD 的语义判断最好；"
            "中文内容也能算，但会把「Java 后端」和「前端开发」这类中文表述判得偏模糊，语义分偏低。"
        ),
    },
    MULTILINGUAL_MODEL: {
        "label": MULTILINGUAL_MODEL,
        "short": "multilingual-MiniLM-L12 · 中英通用",
        "tag": "中文推荐 · 约 470MB",
        "desc": (
            "支持 50+ 种语言，中文简历 / 中文 JD（含中英混排）的语义匹配明显更准，"
            "适合投国内岗位。"
            "<br>代价：模型大约 5 倍大，首次使用需要联网下载约 470MB，之后同样可离线运行。"
        ),
    },
}

st.set_page_config(page_title=f"{APP_NAME} · {APP_NAME_CN}", page_icon="🧭", layout="wide")

# ---------------------------------------------------------------------------
# 样式
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
      .stApp {
        background: radial-gradient(1200px 620px at 8% 0%, #131A24 0%, #0E1117 45%, #0B0F14 100%) !important;
      }
      /* 带边框容器 = 卡片 */
      div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #161B22;
        border: 1px solid rgba(255,255,255,0.07) !important;
        border-radius: 16px;
        box-shadow: 0 6px 16px rgba(0,0,0,0.28);
        padding: 4px 6px;
      }
      h1, h2, h3 { letter-spacing: .2px; }
      .subtle { opacity: .78; }
      .hero {
        text-align:center; margin: 6px 0 10px 0;
      }
      .hero .title { font-size: 38px; font-weight: 800; line-height: 1.2; }
      .hero .title span { color:#00A8E8; }
      .hero .sub { margin-top: 8px; font-size: 15px; opacity:.8; }
      .badge {
        display:inline-block; padding: 2px 10px; border-radius: 999px;
        background: rgba(0,168,232,.14); color:#5CC8F5; font-size: 12px;
        border: 1px solid rgba(0,168,232,.35); margin-right: 6px;
      }
      .skill-hit { color:#7EE787; font-weight:600; }
      .skill-miss { color:#FFA657; font-weight:600; }
      .stButton>button { border-radius: 12px; padding: 0.5rem 1.1rem; font-weight: 600; }
      section[data-testid="stSidebar"] {
        background: #0B1220 !important;
        border-right: 1px solid rgba(255,255,255,0.06);
      }
    </style>
    """,
    unsafe_allow_html=True,
)

_css_path = BASE_DIR / "style.css"
if _css_path.exists():
    with open(_css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="hero">
      <div class="title">🧭 <span>{APP_NAME}</span></div>
      <div class="sub">{APP_NAME_CN} · 简历匹配分析 · 技能缺口 · AI 模拟面试 · 求职建议</div>
      <div style="margin-top:10px;">
        <span class="badge">Sentence Transformers</span>
        <span class="badge">语义匹配</span>
        <span class="badge">技能缺口分析</span>
        <span class="badge">AI 模拟面试</span>
        <span class="badge">Streamlit</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


@contextmanager
def card(title: str):
    """统一样式的卡片容器。"""
    with st.container(border=True):
        st.markdown(f"#### {title}")
        yield


# ---------------------------------------------------------------------------
# LLM 配置
# ---------------------------------------------------------------------------
def _secret(key: str):
    try:
        return st.secrets.get(key)  # type: ignore[attr-defined]
    except Exception:
        return None


with st.sidebar:
    st.markdown("### ⚙️ 设置")

    with st.expander("🤖 LLM 配置（可选）", expanded=False):
        st.caption("不填也能用：所有分析功能都有离线基础模式。填入后自动升级为 AI 模式。")
        api_key_input = st.text_input(
            "API Key",
            type="password",
            placeholder="sk-... / 你的大模型 Key",
            help="支持任意 OpenAI 兼容接口：OpenAI、DeepSeek、通义、Moonshot、本地 vLLM 等",
        )
        base_url_input = st.text_input(
            "Base URL（可选）",
            placeholder="https://api.deepseek.com/v1",
            help="留空则使用 OpenAI 官方接口",
        )
        model_input = st.text_input("模型名（可选）", placeholder="gpt-4o-mini / deepseek-chat")

    with st.expander("🧠 向量模型", expanded=True):
        st.caption("向量模型决定「语义匹配度」这一项的计算方式，换模型后需要重新点一次「开始分析」。")

        model_choice = st.radio(
            "选择 embedding 模型",
            list(EMBED_MODEL_INFO.keys()),
            index=0,
            format_func=lambda m: EMBED_MODEL_INFO[m]["short"],
            help="英文简历选第一个；中文简历、或中英文混合的 JD 选第二个",
        )

        # 每个模型都给一段独立说明，而不是只解释其中一个
        for name, info in EMBED_MODEL_INFO.items():
            picked = name == model_choice
            st.markdown(
                f"{'🟢' if picked else '⚪'} **{info['label']}**　`{info['tag']}`\n\n"
                f"<div style='font-size:12.5px;line-height:1.55;opacity:{1 if picked else .62};"
                f"margin:-6px 0 10px 6px;'>{info['desc']}</div>",
                unsafe_allow_html=True,
            )

        st.caption(f"当前使用：`{model_choice}`")

    llm_config = resolve_config(
        api_key=api_key_input or _secret("OPENAI_API_KEY"),
        base_url=base_url_input or _secret("OPENAI_BASE_URL"),
        model=model_input or _secret("OPENAI_MODEL"),
    )
    ai_ready = is_configured(llm_config)

    if ai_ready:
        st.success(f"AI 模式已开启 · {llm_config['model']}")
    else:
        st.info("当前为**基础模式**（无需 API Key）。填写 API Key 可启用 AI 面试题、AI 简历优化。")

    st.divider()
    st.markdown("### 📌 关于")
    st.write(
        "基于 NLP 语义匹配 + 技能缺口分析的求职助手：计算简历与岗位 JD 的匹配度，"
        "发现缺失技能，生成个性化面试题与简历优化建议。"
    )
    st.caption(
        "匹配度 = 语义相似度 × 60% + 技能覆盖率 × 40%。"
        "分数是启发式指标，仅作参考，请务必只写真实经历。"
    )


# ---------------------------------------------------------------------------
# 输入区
# ---------------------------------------------------------------------------
def load_sample_jd() -> str:
    path = BASE_DIR / "sample_data" / "jd_swe_intern.txt"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return f.read()
    return ""


with st.container(border=True):
    st.markdown("#### 📥 第一步：上传简历并粘贴岗位 JD")
    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        up = st.file_uploader("📎 上传简历（仅支持 PDF）", type=["pdf"])
        if up is not None:
            st.caption(f"已上传：`{up.name}`")
        else:
            st.caption("提示：实习/校招简历建议控制在 1 页。")

    with col_right:
        jd_default = st.session_state.get("jd_text_input", "")
        jd = st.text_area(
            "📄 目标岗位 JD",
            value=jd_default,
            height=190,
            placeholder="把招聘网站上的岗位描述整段粘贴进来...",
        )

    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 3])
    with btn_col1:
        run_btn = st.button("🚀 开始分析", type="primary", use_container_width=True)
    with btn_col2:
        sample_btn = st.button("载入示例 JD", use_container_width=True)

if sample_btn:
    st.session_state["jd_text_input"] = load_sample_jd()
    st.rerun()


# ---------------------------------------------------------------------------
# 分析主流程
# ---------------------------------------------------------------------------
def run_analysis(uploaded, jd_raw: str, model_name: str) -> dict:
    """执行完整分析，返回结果字典。"""
    resume_raw = normalize_lines(read_pdf(uploaded))
    resume_text = clean_text(resume_raw)
    jd_text = clean_text(jd_raw)

    gap = skill_gap(jd_text, resume_text)

    used_embedding = True
    embed_error = ""
    semantic = 0.0
    try:
        r_vec = embed_single(resume_text, model_name)
        j_vec = embed_single(jd_text, model_name)
        semantic = similarity(r_vec, j_vec)
    except Exception as exc:  # 模型下载失败 / 本地无网络等
        used_embedding = False
        embed_error = f"{type(exc).__name__}: {exc}"
        semantic = lexical_overlap(jd_text, resume_text)

    coverage = float(gap["coverage"])  # type: ignore[arg-type]
    overall = combine_score(semantic, coverage, used_embedding)
    ats_issues = basic_ats_checks(resume_text, filename=uploaded.name)

    return {
        "resume_raw": resume_raw,
        "resume_text": resume_text,
        "jd_text": jd_text,
        "filename": uploaded.name,
        "gap": gap,
        "semantic": semantic,
        "coverage": coverage,
        "overall": overall,
        "used_embedding": used_embedding,
        "embed_error": embed_error,
        "ats_issues": ats_issues,
        "model_name": model_name,
        "word_gaps": highlight_tokens(jd_text, resume_text),
        "bullets": extract_bullets(resume_raw),
    }


if run_btn:
    if not jd.strip():
        st.error("请先粘贴岗位 JD。")
    elif up is None:
        st.error("请先上传 PDF 简历。")
    else:
        with st.spinner("正在解析简历并计算匹配度…（首次运行会加载本地向量模型）"):
            try:
                st.session_state["analysis"] = run_analysis(up, jd, model_choice)
                # 新分析 = 清空旧的衍生结果
                for key in ("questions", "advice_md", "report_md", "questions_mode", "advice_mode"):
                    st.session_state.pop(key, None)
            except Exception as exc:
                st.error(f"分析失败：{type(exc).__name__} - {exc}")
                st.stop()

        st.success("✅ 分析完成，下面四个标签页都可以用了。")

analysis = st.session_state.get("analysis")

if not analysis:
    st.info("👆 上传简历、粘贴 JD 后点击「开始分析」，即可解锁简历分析、AI 模拟面试、简历优化和求职报告。")
    st.stop()

# 让后续模块拿到统一的上下文
resume_text = analysis["resume_text"]
resume_raw = analysis["resume_raw"]
jd_text = analysis["jd_text"]
gap = analysis["gap"]
ats_issues = analysis["ats_issues"]

tab_match, tab_interview, tab_rewrite, tab_report = st.tabs(
    ["🎯 简历分析", "🎤 AI 模拟面试", "✏️ 简历优化", "📊 求职报告"]
)

# ---------------------------------------------------------------------------
# Tab 1 简历分析
# ---------------------------------------------------------------------------
with tab_match:
    label, _ = score_label(analysis["overall"])
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 综合匹配度", f"{analysis['overall'] * 100:.1f} / 100")
    c2.metric(
        "🧠 语义匹配度",
        f"{analysis['semantic'] * 100:.1f} / 100",
        "本地 embedding" if analysis["used_embedding"] else "降级：词面重合",
    )
    c3.metric("🔑 技能覆盖率", f"{analysis['coverage'] * 100:.1f} %")

    st.progress(min(max(analysis["overall"], 0.0), 1.0))
    st.caption(f"结论：**{label}**")

    if not analysis["used_embedding"]:
        st.warning(
            "向量模型加载失败，已自动降级为词面重合度计算（功能不中断）。\n\n"
            f"错误：`{analysis['embed_error']}`\n\n"
            "常见原因：首次运行需要下载模型但网络不通。可换用已缓存的 `all-MiniLM-L6-v2` 再试。"
        )

    with card("🔑 技能匹配与缺口分析"):
        missing_map = gap.get("missing", {}) or {}
        required_map = gap.get("required", {}) or {}

        if required_map:
            st.markdown("**岗位要求技能对照**")
            for category, skills in required_map.items():  # type: ignore[union-attr]
                chips = []
                for s in skills:
                    cls = "skill-miss" if s in set(gap.get("missing_list", [])) else "skill-hit"  # type: ignore[arg-type]
                    mark = "❌" if cls == "skill-miss" else "✅"
                    chips.append(f"<span class='{cls}'>{mark} {s}</span>")
                st.markdown(f"- **{category}**：" + "　".join(chips), unsafe_allow_html=True)
        else:
            st.write("未从 JD 中识别出结构化技能（可能是 JD 太短或表述特殊），下面给出词面级缺口。")

        if missing_map:
            st.markdown("**缺失技能（按分类）**")
            for category, skills in missing_map.items():  # type: ignore[union-attr]
                st.markdown(f"- **{category}**：" + "、".join(skills))
        else:
            st.success("岗位要求的技能在简历中都能找到对应表述，没有明显缺口。")

        if analysis["word_gaps"]:
            with st.expander("🔍 词面级补充线索（技能词典之外的词）"):
                st.caption("这些词在 JD 中出现、简历中没有，可能是被忽略的硬性要求。")
                st.write("、".join(analysis["word_gaps"]))

    with card("✅ ATS 与简历卫生检查"):
        if ats_issues:
            for issue in ats_issues:
                if isinstance(issue, (list, tuple)) and len(issue) == 2:
                    st.markdown(f"- **{issue[0]}**：{issue[1]}")
                else:
                    st.markdown(f"- {issue}")
        else:
            st.write("未发现明显的 ATS 问题。")

    with card("✏️ 快捷改写模板（离线）"):
        st.caption("这些是句式模板，用来提醒你怎么写，不是替你编经历。")
        for tip in suggest_bullets("目标岗位", jd_text, analysis["bullets"], list(gap.get("missing_list", []))):  # type: ignore[arg-type]
            st.markdown(f"- {tip}")

# ---------------------------------------------------------------------------
# Tab 2 AI 模拟面试
# ---------------------------------------------------------------------------
with tab_interview:
    with card("🎤 生成个性化面试题"):
        st.write("根据**你的简历**和**目标岗位 JD** 生成面试问题，优先深挖你简历里的项目。")
        c1, c2 = st.columns([1, 3])
        with c1:
            q_count = st.slider("题目数量", 5, 15, 10, step=1)
        with c2:
            mode_now = "AI 模式（大模型生成）" if ai_ready else "基础模式（规则 + 模板）"
            st.caption(f"当前模式：**{mode_now}**")

        gen_btn = st.button("生成面试题", type="primary")

    if gen_btn:
        with st.spinner("正在生成面试题…"):
            questions, used_llm, err = [], False, ""
            if ai_ready:
                try:
                    questions = produce_llm_questions(resume_text, jd_text, gap, llm_config, q_count)
                    used_llm = True
                except LLMError as exc:
                    err = str(exc)
            if not questions:
                questions = generate_questions(resume_raw, resume_text, jd_text, gap, q_count)
                used_llm = False
            st.session_state["questions"] = questions
            st.session_state["questions_mode"] = "AI 模式" if used_llm else "基础模式"
            st.session_state["questions_err"] = err

    if st.session_state.get("questions"):
        if st.session_state.get("questions_err"):
            st.warning(
                f"AI 生成失败，已自动回退到基础模式。原因：{st.session_state['questions_err']}"
            )
        elif st.session_state.get("questions_mode") == "AI 模式":
            st.success("面试题由 AI 生成。")

        questions = st.session_state["questions"]
        with card(f"📝 面试题清单（{len(questions)} 题 · {st.session_state.get('questions_mode')}）"):
            current = None
            for idx, item in enumerate(questions):
                if item["category"] != current:
                    current = item["category"]
                    st.markdown(f"**{current}**")
                st.markdown(f"**{idx + 1}. {item['question']}**")
                st.caption(f"出题依据：{item.get('basis', '—')}")
                with st.expander("✍️ 练习回答并获取点评"):
                    answer_key = f"ans_{idx}"
                    fb_key = f"fb_{idx}"
                    st.text_area("你的回答", key=answer_key, height=140, placeholder="先自己想一遍，再让 AI 点评…")
                    if st.button("提交点评", key=f"btn_{idx}"):
                        if not ai_ready:
                            st.info("点评功能需要 API Key。当前为基础模式，可对照上面的「出题依据」自查。")
                        else:
                            try:
                                with st.spinner("AI 正在点评…"):
                                    st.session_state[fb_key] = review_answer(
                                        item["question"], st.session_state.get(answer_key, ""), jd_text, llm_config
                                    )
                            except LLMError as exc:
                                st.error(f"点评失败：{exc}")
                    if st.session_state.get(fb_key):
                        st.markdown(st.session_state[fb_key])

            st.download_button(
                "💾 下载面试题清单（.md）",
                data=render_questions_markdown(questions).encode("utf-8"),
                file_name="interview_questions.md",
                mime="text/markdown",
            )
    else:
        st.info("点击「生成面试题」，系统会结合你的简历项目、岗位技能要求和技能缺口出题。")

# ---------------------------------------------------------------------------
# Tab 3 简历优化
# ---------------------------------------------------------------------------
with tab_rewrite:
    with card("✏️ 针对岗位的简历优化"):
        st.write("优化方向来自两处：**岗位要求但简历缺失的关键词**，以及 **AI/规则对具体描述的改写建议**。")

        missing_list = list(gap.get("missing_list", []))  # type: ignore[arg-type]
        if missing_list:
            st.markdown("**先在简历里补这些关键词（仅在真实具备时）**")
            st.markdown("　" + "　".join(f"`{s}`" for s in missing_list))
        else:
            st.success("岗位要求的关键词简历都已覆盖，重点放在描述的量化表达上。")

        st.divider()
        st.markdown("**选择一条简历描述进行优化**")
        bullets = analysis["bullets"] or [""]
        chosen = st.selectbox("从简历中自动抽取的描述", options=range(len(bullets)), format_func=lambda i: bullets[i][:80] or "（空）")
        manual = st.text_area("或者直接粘贴你想优化的那段描述", height=120, placeholder="例如：负责投票系统的后端开发…")

        target_bullet = manual.strip() or bullets[chosen]

        col_a, col_b = st.columns([1, 1])
        with col_a:
            rewrite_btn = st.button("🤖 用 AI 优化这段描述", type="primary", use_container_width=True)
        with col_b:
            if not ai_ready:
                st.caption("未配置 API Key：按钮会提示，可先用右侧的离线模板。")

        if rewrite_btn:
            if not ai_ready:
                st.warning("AI 优化需要 API Key，请在左侧「LLM 配置」里填写。下面给出离线改写思路。")
                st.markdown(
                    "- **结构**：动词 + 做了什么 + 用了什么技术 + 结果（数字）\n"
                    "- **动词**：设计 / 实现 / 优化 / 重构 / 部署 / 主导，替换掉「负责」「参与」\n"
                    "- **对齐 JD**：把 JD 里的关键词替换进你真实做过的工作描述中\n"
                    f"- **本次可补的关键词**：{'、'.join(missing_list[:6]) or '无'}"
                )
            elif not target_bullet:
                st.error("请先选择或粘贴一段需要优化的描述。")
            else:
                try:
                    with st.spinner("AI 正在改写…"):
                        st.session_state["rewrite_result"] = produce_llm_bullet_rewrite(
                            target_bullet, jd_text, missing_list, llm_config
                        )
                except LLMError as exc:
                    st.error(f"改写失败：{exc}")

        if st.session_state.get("rewrite_result"):
            st.markdown(st.session_state["rewrite_result"])

    with card("⚠️ 改写红线"):
        st.markdown(
            "- 只能优化**表达方式**，不能新增项目、公司、技术或虚假数据指标；\n"
            "- 缺少量化数据时用 `[请填写具体数据]` 占位，自己补上真实数字；\n"
            "- 面试时每一句都要能讲清楚，写不出来的话就是不该写的话。"
        )

# ---------------------------------------------------------------------------
# Tab 4 求职报告
# ---------------------------------------------------------------------------
with tab_report:
    with card("📊 综合求职报告"):
        st.write("把匹配度、技能缺口、ATS 问题、优化建议和面试题汇总成一份可下载的报告。")

        c1, c2 = st.columns([1, 1])
        with c1:
            make_report = st.button("生成报告", type="primary", use_container_width=True)
        with c2:
            use_llm_advice = st.checkbox(
                "用 AI 生成个性化求职建议", value=ai_ready, disabled=not ai_ready,
                help="需要 API Key；关闭则使用离线规则建议",
            )

    if make_report:
        advice_mode = "基础模式（离线规则）"
        advice_md = ""
        if use_llm_advice and ai_ready:
            try:
                with st.spinner("AI 正在生成求职建议…"):
                    advice_md = produce_llm_advice(resume_text, jd_text, gap, ats_issues, llm_config)
                advice_mode = f"AI 模式（{llm_config['model']}）"
            except LLMError as exc:
                st.warning(f"AI 建议生成失败，已回退基础模式：{exc}")

        if not advice_md:
            advice_md = render_advice_markdown(
                build_strengths(gap, analysis["semantic"], analysis["coverage"]),
                build_resume_tips(gap, ats_issues),
                build_interview_focus(gap),
                advice_mode,
            )

        questions = st.session_state.get("questions") or generate_questions(
            resume_raw, resume_text, jd_text, gap, 10
        )

        report_md = build_full_report(
            semantic_score=analysis["semantic"],
            coverage=analysis["coverage"],
            overall_score=analysis["overall"],
            gap=gap,
            ats_issues=ats_issues,
            questions=questions,
            advice_markdown=advice_md,
            model_name=analysis["model_name"],
            llm_mode=advice_mode,
        )
        st.session_state["advice_md"] = advice_md
        st.session_state["report_md"] = report_md
        st.session_state["advice_mode"] = advice_mode

    if st.session_state.get("report_md"):
        st.success(f"报告已生成 · 建议来源：{st.session_state.get('advice_mode')}")
        with card("👀 报告预览"):
            st.markdown(st.session_state["report_md"])
        st.download_button(
            "💾 下载报告（.md，可直接粘进 Word / 转 PDF）",
            data=st.session_state["report_md"].encode("utf-8"),
            file_name=f"career_copilot_report_{analysis['filename'].rsplit('.', 1)[0]}.md",
            mime="text/markdown",
        )
    else:
        st.info("点击「生成报告」，即可得到包含匹配度、缺口、建议与面试题的完整报告。")
