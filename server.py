"""
AI 文游游戏厅 - 后端服务
========================
功能：
    1. 自动扫描 games/ 目录下的 .docx 文件作为游戏列表
    2. 代理调用豆包/OpenAI兼容 API 进行流式对话
    3. 每个游戏的 prompt（docx 内容）作为 system message 注入
    4. 支持会话记忆（服务端维护对话历史）

部署：
    pip install fastapi uvicorn python-docx openai python-dotenv
    python server.py
"""

import os
import uuid
import hashlib
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from docx import Document
from openai import AsyncOpenAI

load_dotenv()

# ============================================================
# 配置
# ============================================================

# 豆包 API（字节火山引擎）—— 兼容 OpenAI 接口格式
# 也可以替换为任何 OpenAI 兼容的 API（如 DeepSeek、Kimi 等）
API_KEY = os.getenv("API_KEY", "")
API_BASE_URL = os.getenv("API_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
MODEL_NAME = os.getenv("MODEL_NAME", "doubao-1-5-pro-256k-250115")

# 游戏 docx 文件目录
GAMES_DIR = Path(os.getenv("GAMES_DIR", "./games"))

# 头像目录
AVATARS_DIR = Path(os.getenv("AVATARS_DIR", "./avatars"))

# 对话历史最大轮数（防止 token 溢出）
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "50"))

# ============================================================
# 全局状态
# ============================================================

# 游戏缓存: game_id -> {name, prompt, file_path}
games_cache: dict = {}

# 会话存储: session_id -> {game_id, messages: [...]}
sessions: dict = {}


def get_avatar_list() -> list:
    """获取 avatars/ 目录下所有图片文件"""
    AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
    avatars = [f.name for f in sorted(AVATARS_DIR.iterdir()) if f.suffix.lower() in exts]
    return avatars


def assign_avatar(game_id: str) -> Optional[str]:
    """根据 game_id 哈希稳定分配一个头像文件名，无头像时返回 None"""
    avatars = get_avatar_list()
    if not avatars:
        return None
    index = int(hashlib.md5(game_id.encode()).hexdigest(), 16) % len(avatars)
    return avatars[index]


def load_games():
    """扫描 games/ 目录，加载所有 docx 文件"""
    global games_cache
    games_cache = {}

    if not GAMES_DIR.exists():
        GAMES_DIR.mkdir(parents=True, exist_ok=True)
        return

    for docx_file in sorted(GAMES_DIR.glob("*.docx")):
        try:
            # 生成稳定的 game_id（基于文件名哈希）
            game_id = hashlib.md5(docx_file.name.encode()).hexdigest()[:8]

            # 提取游戏名（去掉序号前缀）
            name = docx_file.stem.lstrip("0123456789.").strip()
            if not name:
                name = docx_file.stem

            # 读取 docx 内容作为 prompt
            doc = Document(str(docx_file))
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            prompt = "\n".join(paragraphs)

            if prompt:
                games_cache[game_id] = {
                    "name": name,
                    "prompt": prompt,
                    "file": docx_file.name,
                    "avatar": assign_avatar(game_id),
                }
        except Exception as e:
            print(f"⚠️  加载失败 {docx_file.name}: {e}")

    print(f"📂 已加载 {len(games_cache)} 个游戏")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时加载游戏"""
    load_games()
    yield


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(title="AI文游游戏厅", lifespan=lifespan)

# 允许跨域（方便本地开发）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API 路由
# ============================================================


class ChatRequest(BaseModel):
    session_id: str
    game_id: str
    message: str


@app.get("/api/games")
async def list_games():
    """获取所有游戏列表"""
    # 每次请求都重新扫描，这样丢新 docx 进去刷新就能看到
    load_games()
    return [
        {
            "id": gid,
            "name": info["name"],
            "avatar": f"/api/avatars/{info['avatar']}" if info.get("avatar") else None,
        }
        for gid, info in games_cache.items()
    ]


@app.get("/api/avatars/{filename}")
async def get_avatar(filename: str):
    """返回头像图片文件"""
    file_path = AVATARS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "头像不存在")
    return FileResponse(file_path)


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """发送消息并获取 AI 流式回复"""
    if not API_KEY:
        raise HTTPException(500, "未配置 API_KEY，请在 .env 中设置")

    game = games_cache.get(req.game_id)
    if not game:
        raise HTTPException(404, f"游戏不存在: {req.game_id}")

    # 获取或创建会话
    if req.session_id not in sessions:
        sessions[req.session_id] = {
            "game_id": req.game_id,
            "messages": []
        }

    session = sessions[req.session_id]

    # 如果切换了游戏，重置历史
    if session["game_id"] != req.game_id:
        session["game_id"] = req.game_id
        session["messages"] = []

    # 添加用户消息
    session["messages"].append({"role": "user", "content": req.message})

    # 保持历史在限制内
    if len(session["messages"]) > MAX_HISTORY_TURNS * 2:
        session["messages"] = session["messages"][-(MAX_HISTORY_TURNS * 2):]

    # 构建完整消息列表（system prompt + 历史）
    messages = [
        {"role": "system", "content": game["prompt"]},
        *session["messages"]
    ]

    # 调用 AI API（流式）
    client = AsyncOpenAI(api_key=API_KEY, base_url=API_BASE_URL)

    async def generate():
        assistant_content = ""
        try:
            stream = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                stream=True,
                temperature=0.9,
                max_tokens=2048,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    assistant_content += content
                    yield f"data: {content}\n\n"

            # 流结束，保存 assistant 回复到历史
            session["messages"].append({"role": "assistant", "content": assistant_content})
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/reset")
async def reset_session(session_id: str, game_id: str):
    """重置某个会话的对话历史"""
    key = session_id
    if key in sessions:
        sessions[key]["messages"] = []
    return {"status": "ok"}


@app.get("/api/new-session")
async def new_session():
    """生成一个新的 session_id"""
    return {"session_id": str(uuid.uuid4())}


@app.post("/api/upload")
async def upload_game(file: UploadFile = File(...)):
    """上传 .docx 游戏文件到 games/ 目录"""
    if not file.filename:
        raise HTTPException(400, "文件名为空")

    # 只接受 .docx 文件
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "只支持 .docx 格式的文件哦~")

    # 确保 games 目录存在
    GAMES_DIR.mkdir(parents=True, exist_ok=True)

    # 保存文件
    save_path = GAMES_DIR / file.filename
    content = await file.read()

    # 文件大小限制（10MB）
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "文件太大了，最大支持 10MB")

    # 验证是否为有效的 docx（尝试解析）
    import io
    try:
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        if not paragraphs:
            raise HTTPException(400, "这个文件里没有文字内容哦")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "无法识别这个文件，请确认是 .docx 格式")

    # 写入文件
    with open(save_path, "wb") as f:
        f.write(content)

    # 提取游戏名
    name = save_path.stem.lstrip("0123456789.").strip()
    if not name:
        name = save_path.stem

    # 刷新游戏缓存
    load_games()

    return {"status": "ok", "name": name, "file": file.filename}


@app.delete("/api/games/{game_id}")
async def delete_game(game_id: str):
    """删除一个游戏"""
    game = games_cache.get(game_id)
    if not game:
        raise HTTPException(404, "游戏不存在")

    # 删除文件
    file_path = GAMES_DIR / game["file"]
    if file_path.exists():
        file_path.unlink()

    # 刷新缓存
    load_games()
    return {"status": "ok"}


# ============================================================
# 静态文件 & 前端
# ============================================================

# 优先响应 API，其余走静态文件
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """返回前端页面"""
    index_path = Path(__file__).parent / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>AI文游游戏厅</h1><p>index.html 不存在</p>")


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    print(f"🎮 AI文游游戏厅启动中...")
    print(f"📍 访问地址: http://localhost:{port}")
    print(f"📂 游戏目录: {GAMES_DIR.absolute()}")
    uvicorn.run(app, host="0.0.0.0", port=port)
