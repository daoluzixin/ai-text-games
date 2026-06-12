# AI 文游游戏厅 🎮

自托管的 AI 文字冒险游戏平台。上传 `.docx` 格式的游戏剧本，AI 会始终记住角色设定，不再"失忆"。

线上体验：http://39.106.187.120:8080

## 功能特点

- 📄 上传 `.docx` 剧本文件作为永久系统提示词
- 💬 流式对话，实时打字效果
- 🎭 自动分配角色头像（基于游戏名哈希，每次稳定一致）
- 🎨 四套主题风格：梦幻薰衣草（默认）、哥特暗夜、赛博霓虹、森林精灵
- 🔊 Web Audio API 合成音效系统（BGM / 点击 / 提示 / 打字音），零外部音频文件
- 📊 RPG 属性自动进度条（好感度、忠诚、体力等自动检测渲染）
- 💾 多存档系统，支持浏览器刷新后自动恢复游戏状态
- ⚡ 渐进式渲染，读档瞬间显示内容、后台异步升级富文本
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

### 4. 服务器部署

```bash
# 直接 scp 上传后用 systemd 管理
scp index.html server.py static/md-frame.html root@your-server:/path/to/app/
ssh root@your-server "systemctl restart ai-text-games"
```

## 使用方法

1. 打开网页，点击「上传新游戏」
2. 选择一个 `.docx` 格式的游戏剧本文件
3. 点击游戏卡片开始冒险
4. AI 会根据剧本中的角色设定与你互动，永远不会忘记设定
5. 右上角可切换主题风格和音效设置

## 主题系统

| 主题 | 风格 | 配色 |
|------|------|------|
| 梦幻薰衣草 | 温柔梦幻 | 紫粉渐变 + 星光粒子 |
| 哥特暗夜 | 暗黑神秘 | 深紫黑 + 红色高亮 |
| 赛博霓虹 | 科幻未来 | 深蓝 + 霓虹青粉 |
| 森林精灵 | 自然清新 | 翠绿 + 金色光斑 |

每个主题包含独立的 CSS 变量、背景粒子动画和 BGM 调性。

## 音效系统

全部使用 Web Audio API 程序化合成，无需加载任何音频文件：

- **背景音乐**：根据当前主题自动切换调性（薰衣草=C大调、哥特=A小调、赛博=电子、森林=D大调）
- **按钮点击**：水滴感下降音
- **收到回复**：柔和大三度双音叮咚
- **AI 打字**：极轻触感白噪声脉冲

右上角 🔊 面板可独立控制音效/BGM 开关和音量。

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

## 项目结构

```
├── server.py              # 后端主文件（FastAPI + SSE + 游戏管理）
├── index.html             # 前端 SPA（主题/音效/存档/对话）
├── static/md-frame.html   # iframe 富文本渲染器（进度条/状态卡片）
├── avatars/               # SVG 角色头像
├── games/                 # .docx 游戏剧本（gitignore）
├── docs/                  # 项目文档与执行计划
│   ├── agents/            # Agent 导引文档
│   └── exec-plans/        # 执行计划与日志
├── scripts/               # 工具脚本（lint 等）
├── Dockerfile             # 容器化部署
└── docker-compose.yml     # 编排配置
```

## 技术栈

- 后端：FastAPI + python-docx + SSE + SQLite
- 前端：原生 HTML/CSS/JS（无框架依赖）+ Web Audio API
- 渲染：iframe 沙箱 + XML 状态卡片 + 自动进度条
- 部署：Docker / systemd + 阿里云 ECS

## License

MIT
