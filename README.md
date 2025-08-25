# Gemini 聊天记录分析器

这是一个功能强大的本地工具，用于解析、处理和深度分析您的 Google Gemini 聊天记录。它不仅能将您的 HTML 聊天记录转换为结构化的 JSON 和易于阅读的 TXT 文件，还提供了一个基于 Web 的交互式仪表盘，帮助您从多个维度洞察自己的对话模式和兴趣所在。

---

## ✨ 主要功能

- **HTML 解析**: 自动从 Google 导出的 `我的活动记录.html` 文件中提取完整的对话历史。
- **AI 智能打标**: 
    - 支持 **Google Gemini** 和 **OpenAI 兼容 API** (如 Groq, Deepseek 等)。
    - 为每段对话自动生成简洁的**索引标题**和**关键词标签**。
    - 支持**多 API 密钥轮询**，有效处理大量数据，避免速率限制。
- **多种输出格式**: 
    - `processed_history.json`: 结构化的 JSON 文件，便于程序进一步处理。
    - `processed_history.txt`: 格式化为人类可读的 TXT 文件，方便快速查阅。
- **交互式 Web 分析仪表盘**: 
    - **高频词云**: 直观展示您最常讨论的主题。
    - **多维度图表**: 包括兴趣分布、对话趋势、内容长度分布等。
    - **详细统计**: 提供热门词汇、热门标签和情感倾向分析。
    - **数据筛选**: 可按时间范围（周/月）和分析对象（用户/AI/全部）进行筛选。
- **安全与隐私**: 所有数据均在本地处理，通过 `.gitignore` 文件严格保护您的 API 密钥和聊天记录不被意外上传。
- **灵活配置**: 通过 `settings.json` 轻松切换 AI 服务商和配置模型参数。

---

## 🚀 项目结构

本项目主要由两部分组成：

1.  **`data_pipeline.py` (数据处理流水线)**
    - 这是核心脚本，负责读取 HTML 文件，调用 AI 进行分析和打标，并生成初始的数据文件 (`processed_history.json` 和 `processed_history.txt`)。

2.  **`聊天记录分析/` (Web 分析应用)**
    - 这是一个基于 Flask 和 Chart.js 的小型 Web 应用。
    - 它会读取 `data_pipeline.py` 生成的 `processed_history.json` 文件，并为您提供一个可视化的分析界面。

---
## 前期准备-记录导出
1.进入账号详细信息
2.进入数据和隐私设置
3.找到“下载或删除您的数据”并点击进入下一页面
4.先取消全选，再选择
Gemini
您的 Gemini Gem 数据，包括名称和指令
和
我的活动
您的活动数据记录（包括图片和音频附件）
（在“我的活动记录”内容选项里面仅选择Gemini Apps即可）
5.打开gmail邮箱等待到官方的邮件选择下载
6.找到我的活动记录.html并备用
## 🛠️ 安装与设置

**1. 克隆项目**

```bash
git clone https://github.com/Qingfeng-233/Google_Gemini-history-analyze.git
cd Google_Gemini-history-analyze
```

**2. 安装依赖**

确保您已安装 Python 3.x。然后安装两个部分所需的库：

```bash
# 安装依赖
pip install -r requirements.txt
```

**3. 配置文件**

- **`settings.json`**: 
    - 打开此文件，将 `ai_provider` 设置为您想使用的服务 (`"gemini"` 或 `"openai"`)。
    - 如果您使用 `openai` 或其他兼容 API，请务必填写正确的 `base_url` 和 `model`。

- **`valid_keys.txt`**: 
    - **(重要)** 在此文件中填入您的 API 密钥，每行一个。脚本会根据您在 `settings.json` 中选择的服务，使用这些密钥进行轮询。

**4. 放置聊天记录**

- 将您从 Google Takeout 导出的聊天记录文件命名为 `我的活动记录.html`，并将其放置在项目的根目录下。

---

## 🏃‍♂️ 如何使用

### 第一步：运行数据处理流水线

在项目根目录下，运行 `data_pipeline.py`。

```bash
python data_pipeline.py
```

- 脚本会启动，并显示分步确认提示。您只需按照提示按 `Enter` 键即可继续。
- 成功运行后，会在根目录下生成 `processed_history.json` 和 `processed_history.txt` 文件。

### 第二步：启动 Web 分析应用

进入 `聊天记录分析` 目录并运行 `app.py`。

```bash
cd 聊天记录分析
python app.py
```

- 终端会显示服务已在 `http://127.0.0.1:5000` 上运行。
- 在您的浏览器中打开此地址，即可看到您的个人聊天分析报告！


---

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)。详情请参阅 `LICENSE` 文件。
