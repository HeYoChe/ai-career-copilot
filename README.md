# 🧭 AI Career Copilot · AI 智能求职助手

> 一个基于 **NLP 语义匹配 + 技能缺口分析** 的求职助手：把你的简历和目标岗位 JD 丢进来，
> 它会给出匹配度评分、缺失技能清单、ATS 体检结果、个性化面试题和简历优化建议。

---

## ✨ 功能

| 模块 | 说明 |
| --- | --- |
| 🎯 **简历-JD 智能匹配** | 用 Sentence Transformers 把简历和 JD 转成向量，余弦相似度计算语义匹配度 |
| 🔑 **技能缺口分析** | 内置 8 大类中英文技能词典，输出「岗位要求 / 已具备 / 缺失」三组技能 + 覆盖率 |
| ✅ **ATS 与简历卫生检查** | 文件名规范、联系方式、LinkedIn/GitHub、篇幅、必备章节 |
| 🎤 **AI 模拟面试** | 结合简历项目、JD 技能要求和技能缺口，动态生成分类面试题（项目深挖 / 技术基础 / 技能缺口 / 岗位匹配 / 行为面试） |
| ✍️ **回答点评**（需 API Key） | 提交你的回答，AI 给出优点 / 问题 / 改进建议 / 参考要点 |
| ✏️ **简历优化** | 基于缺口关键词给出改写方向；配置 API Key 后可由 LLM 改写单条描述（禁止虚构事实） |
| 📊 **求职报告** | 一键汇总匹配度、技能盘点、ATS 问题、优化建议和面试题，导出 Markdown |

### 双模式设计

- **基础模式**：不需要任何 API Key，全部功能可用（面试题走规则 + 模板，建议走离线规则）。
- **AI 模式**：填入任意 **OpenAI 兼容** 接口的 Key，即可获得大模型生成的面试题、回答点评与简历改写。
  LLM 调用失败会自动回退基础模式，不会让 Demo 挂掉。

---

## 📐 综合匹配度怎么算

```
综合匹配度 = 语义匹配度 × 60% + 技能覆盖率 × 40%
```

- **语义匹配度**：`all-MiniLM-L6-v2` 句向量的余弦相似度，衡量整体表述的相关性（能识别同义表达）。
- **技能覆盖率**：JD 中识别到的技能里，有多少能在简历中找到（对齐 ATS 的硬性关键词筛选）。
- 若本地向量模型不可用，会自动降级为词面重合度，功能不中断。

> 为什么不用纯关键词匹配？关键词匹配会漏掉 "machine learning" vs "ML" 这类同义表达；
> 而纯语义匹配又会漏掉 ATS 真正在扫的硬技能名。所以这里两者结合，并且**拆开展示**，每个数字都能解释。

---

## 🛠 技术栈

| 层 | 技术 |
| --- | --- |
| Web 应用 | Streamlit |
| NLP / Embedding | sentence-transformers（all-MiniLM-L6-v2 / 可选多语言模型） |
| 相似度计算 | scikit-learn cosine_similarity、numpy |
| PDF 解析 | pdfplumber |
| 技能抽取 | 自建中英文技能分类词典 + 正则边界匹配 |
| LLM（可选） | openai SDK ≥ 1.0，兼容 OpenAI / DeepSeek / 通义 / Moonshot / 本地 vLLM |
| 配置 | python-dotenv |

---

## 🗂 项目结构

```
ai-career-copilot/
├─ app.py                  # Streamlit 主程序：四个标签页 + 分析主流程
├─ style.css               # 自定义样式
├─ requirements.txt
├─ .env.example            # 环境变量模板
├─ .streamlit/config.toml  # 深色主题配置
├─ src/
│  ├─ extract.py           # PDF 解析、文本清洗、bullet 抽取
│  ├─ embed.py             # 句向量（模型可切换、按名缓存）
│  ├─ match.py             # 余弦相似度、关键词 token 化
│  ├─ skills.py            # 技能词典 + 技能缺口分析
│  ├─ scoring.py           # 综合评分、降级策略、词面缺口
│  ├─ ats.py               # ATS 与简历卫生检查
│  ├─ interview.py         # 面试题生成（规则 + LLM）、回答点评
│  ├─ advice.py            # 求职建议、LLM 简历改写
│  ├─ llm.py               # LLM 统一封装（含降级与错误处理）
│  ├─ rewrite.py           # 离线改写模板
│  └─ report.py            # Markdown 报告生成
└─ sample_data/
   └─ jd_swe_intern.txt    # 示例 JD
```

### 数据流

```
上传 PDF ──► extract（解析+清洗）─┐
粘贴 JD  ──► extract（清洗）─────┤
                                 ├─► embed（句向量）──► match（余弦相似度）┐
                                 │                                        ├─► scoring（综合分）
                                 └─► skills（技能抽取）──► 技能覆盖率 ────┘
                                          │
                                          ├─► ats（体检）
                                          ├─► interview（面试题：规则 / LLM）
                                          ├─► advice（建议：规则 / LLM）
                                          └─► report（Markdown 报告）
```

---

## 🚀 运行方法

### 1. 安装依赖

```bash
# 建议先创建虚拟环境
python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

python -m pip install -r requirements.txt
```

### 2. 启动

```bash
python -m streamlit run app.py
```

浏览器打开终端里显示的地址（默认 http://localhost:8501）。

> 建议用 `python -m streamlit` 而不是直接敲 `streamlit`：前者不依赖 PATH 和 `Scripts` 目录，
> 换机器、换路径、换虚拟环境都不会失效。

首次运行会加载本地 embedding 模型；如果本地没有缓存，会自动联网下载（约 90MB）。

### 3. 使用

1. 上传 PDF 简历；
2. 粘贴目标岗位 JD（也可以点「载入示例 JD」快速体验）；
3. 点击 **开始分析**；
4. 在四个标签页里查看：简历分析 / AI 模拟面试 / 简历优化 / 求职报告。

---

## 🔑 环境变量（可选）

复制 `.env.example` 为 `.env` 并填写：

```env
OPENAI_API_KEY=你的Key
OPENAI_BASE_URL=          # 可选，填了就切换成兼容接口
OPENAI_MODEL=gpt-4o-mini  # 可选
EMBED_MODEL=all-MiniLM-L6-v2
```

**不填也能用**：所有核心分析都是本地计算的，LLM 只负责「AI 增强」部分。

### 关于中文简历

默认模型 `all-MiniLM-L6-v2` 对英文效果最好。如果简历和 JD 都是中文，
建议在侧边栏或 `EMBED_MODEL` 里换成 `paraphrase-multilingual-MiniLM-L12-v2`
（首次使用需要下载，约 470MB）。

---

## 📦 部署（Streamlit Community Cloud）

全程在浏览器里操作，不需要命令行：

1. 把项目推到一个**公开** GitHub 仓库（确认 `.env`、简历 PDF 没有提交）；
2. 打开 https://share.streamlit.io ，用 GitHub 账号登录并选择该仓库；
3. **Main file path** 填 `app.py`；
4. 展开 **Advanced settings → Secrets**，填入 Key（不需要 AI 功能可留空）：

   ```toml
   # 以 DeepSeek 为例；换其他 OpenAI 兼容平台时改后两行即可
   OPENAI_API_KEY = "sk-你的Key"
   OPENAI_BASE_URL = "https://api.deepseek.com/v1"
   OPENAI_MODEL = "deepseek-chat"
   ```

5. 点 **Deploy**，等待 3～10 分钟构建。

**部署后注意**

- 三个变量要一起填。只填 `OPENAI_API_KEY` 而不填 `OPENAI_BASE_URL`，请求会发往 OpenAI 官方接口，
  鉴权失败后**静默回退基础模式** —— 表现是「界面没有报错，但 AI 功能没反应」。
- 不填任何 Secret 也能正常部署，匹配度 / 技能缺口 / ATS / 规则版面试题全部可用。
- 免费实例内存 1GB，首次点击「开始分析」需下载 embedding 模型（约 90MB），等待 1～2 分钟后恢复正常。
- 简历和 JD 为中文时，建议把 `EMBED_MODEL` 设为 `paraphrase-multilingual-MiniLM-L12-v2`（约 470MB，首次加载较慢）。

---

## ⚠️ 使用须知

- 匹配度和关键词都是**启发式指标**，只作参考，不代表企业 ATS 的真实判定；
- 简历优化功能只改**表达方式**，不会替你编造项目、公司、技术或数据；
- 请只保留真实经历 —— 面试时讲不出来的内容，写上去反而是减分项。

---

## 🗺 未来规划

- [ ] 支持 Word / 纯文本简历导入
- [ ] 岗位收藏与多岗位横向对比
- [ ] 面试回答评分的历史记录与趋势
- [ ] 导出 PDF 版报告

---

## 📄 License

MIT
