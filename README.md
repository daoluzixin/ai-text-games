# AI 文游游戏厅 🎮

自托管的 AI 文字冒险游戏平台。上传 `.docx` 格式的游戏剧本，AI 会始终记住角色设定，不再"失忆"。

## 功能特点

- 📄 上传 `.docx` 剧本文件作为永久系统提示词
- 💬 流式对话，实时打字效果
- 🎭 自动分配角色头像（基于游戏名哈希，每次稳定一致）
- 📱 移动端友好的视觉小说风格界面
- 🔌 支持任何 OpenAI 兼容 API（DeepSeek、通义千问、智谱 GLM 等）
- 🐳 Docker 一键部署

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API 密钥
```

推荐使用 DeepSeek（便宜好用）：
```
API_BASE_URL=https://api.deepseek.com/v1
API_KEY=sk-你的密钥
MODEL_NAME=deepseek-chat
```

### 2. 本地运行

```bash
pip install -r requirements.txt
python3 server.py
```

访问 http://localhost:8000

### 3. Docker 部署

```bash
docker-compose up -d
```

## 使用方法

1. 打开网页，点击「上传新游戏」
2. 选择一个 `.docx` 格式的游戏剧本文件
3. 点击游戏卡片开始冒险
4. AI 会根据剧本中的角色设定与你互动，永远不会忘记设定

## 游戏剧本格式

剧本是普通的 Word 文档（`.docx`），内容就是你想让 AI 扮演的角色设定和游戏规则。例如：

> 你是一个吸血鬼伯爵，住在古堡中。玩家是一个误入古堡的旅人。你要用优雅而神秘的语气与玩家对话，引导他探索古堡的秘密...

## 支持的 AI 后端

| 服务商 | 价格 | 配置 |
|--------|------|------|
| DeepSeek | ¥1-2/百万token | `api.deepseek.com/v1` |
| 通义千问 | 注册送100万token | `dashscope.aliyuncs.com/compatible-mode/v1` |
| 智谱 GLM | GLM-4-Flash 免费 | `open.bigmodel.cn/api/paas/v4` |
| SiliconFlow | 注册送¥14 | `api.siliconflow.cn/v1` |

## 技术栈

- 后端：FastAPI + python-docx + SSE
- 前端：原生 HTML/CSS/JS（无框架依赖）
- 部署：Docker + docker-compose

## License

MIT
