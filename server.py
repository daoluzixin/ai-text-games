"""
AI 文游游戏厅 - 后端服务（路由层）
==================================
职责：定义 API 路由，编排各模块完成业务逻辑。
业务细节分散在 config / prompts / db / games 模块中。

部署：
    pip install fastapi uvicorn python-docx openai python-dotenv
    python server.py
"""

import io
import json
import uuid
import asyncio
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI
from docx import Document

from config import (
    API_KEY, API_BASE_URL, MODEL_NAME,
    MAX_TOKENS, TEMPERATURE,
    SUMMARY_TRIGGER, KEEP_RECENT_MESSAGES,
    GAMES_DIR, AVATARS_DIR, PORT,
)
from prompts import SUMMARY_SYSTEM_PROMPT, CREATIVE_FREEDOM_PROMPT, XML_FORMAT_PROMPT
from db import (
    sessions, init_db, load_sessions_from_db,
    save_session, delete_session_from_db, list_sessions_from_db,
)
from games import games_cache, load_games, pick_random_avatar


# ============================================================
# 应用初始化
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库、恢复会话、加载游戏"""
    init_db()
    load_sessions_from_db()
    load_games()
    yield


app = FastAPI(title="AI文游游戏厅", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 请求模型
# ============================================================

class ChatRequest(BaseModel):
    session_id: str
    game_id: str
    message: str
    avatar: Optional[str] = None


# ============================================================
# 辅助函数
# ============================================================

async def summarize_history(client: AsyncOpenAI, old_summary: str,
                            messages_to_archive: list, game_name: str) -> str:
    """把一批旧消息压缩成新的前情提要。失败时返回旧摘要。"""
    convo_text = "\n".join(
        f"{'玩家' if m['role'] == 'user' else '游戏'}：{m['content']}"
        for m in messages_to_archive
        if m.get("role") in ("user", "assistant")
    )
    user_content = (
        f"【游戏】{game_name}\n\n"
        f"【已有前情提要】\n{old_summary or '（暂无，这是第一次归档）'}\n\n"
        f"【需要归档的最新对话】\n{convo_text}"
    )
    try:
        resp = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            stream=False,
            temperature=0.3,
            max_tokens=600,
        )
        new_summary = (resp.choices[0].message.content or "").strip()
        return new_summary or old_summary
    except Exception as e:
        print(f"⚠️  摘要生成失败，沿用旧摘要：{e}")
        return old_summary


# ============================================================
# API 路由
# ============================================================

@app.get("/api/games")
async def list_games():
    """获取所有游戏列表"""
    load_games()
    return [
        {
            "id": gid,
            "name": info["name"],
            "summary": info.get("summary", ""),
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


@app.get("/api/sessions")
async def list_sessions():
    """列出所有存档（按最后活动时间倒序）"""
    load_games()
    rows = list_sessions_from_db()

    result = []
    for session_id, game_id, messages_json, save_avatar, updated_at in rows:
        try:
            messages = json.loads(messages_json) if messages_json else []
        except (json.JSONDecodeError, TypeError):
            messages = []

        if not messages:
            continue

        game = games_cache.get(game_id)
        last_msg = messages[-1]
        preview = last_msg.get("content", "").strip().replace("\n", " ")
        if len(preview) > 60:
            preview = preview[:60] + "…"

        avatar_url = save_avatar or (
            f"/api/avatars/{game['avatar']}"
            if game and game.get("avatar") else None
        )

        result.append({
            "session_id": session_id,
            "game_id": game_id,
            "game_name": game["name"] if game else "（已删除的游戏）",
            "avatar": avatar_url,
            "game_exists": game is not None,
            "last_played": updated_at,
            "message_count": len(messages),
            "preview": preview,
        })

    return result


@app.get("/api/sessions/{session_id}")
async def get_session_detail(session_id: str):
    """返回某个存档的完整消息历史"""
    if session_id in sessions:
        s = sessions[session_id]
        return {
            "session_id": session_id,
            "game_id": s["game_id"],
            "messages": s["messages"],
            "avatar": s.get("avatar"),
            "last_played": None,
        }

    # 内存没有则回退查数据库
    import sqlite3
    from config import DB_PATH
    conn = sqlite3.connect(str(DB_PATH))
    try:
        row = conn.execute(
            "SELECT game_id, messages, avatar, updated_at FROM sessions "
            "WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {"session_id": session_id, "game_id": None,
                "messages": [], "avatar": None, "last_played": None}

    game_id, messages_json, save_avatar, updated_at = row
    try:
        messages = json.loads(messages_json) if messages_json else []
    except (json.JSONDecodeError, TypeError):
        messages = []

    return {
        "session_id": session_id,
        "game_id": game_id,
        "messages": messages,
        "avatar": save_avatar,
        "last_played": updated_at,
    }


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
            "messages": [],
            "summary": "",
            "avatar": req.avatar,
        }

    session = sessions[req.session_id]
    session.setdefault("summary", "")
    session.setdefault("avatar", None)
    if req.avatar and not session.get("avatar"):
        session["avatar"] = req.avatar

    # 切换游戏时重置
    if session["game_id"] != req.game_id:
        session["game_id"] = req.game_id
        session["messages"] = []
        session["summary"] = ""

    # 添加用户消息并落盘
    session["messages"].append({"role": "user", "content": req.message})
    save_session(req.session_id)

    # 调用 AI（流式）
    client = AsyncOpenAI(api_key=API_KEY, base_url=API_BASE_URL)

    # 滚动摘要
    if len(session["messages"]) > SUMMARY_TRIGGER:
        keep = max(KEEP_RECENT_MESSAGES, 2)
        to_archive = session["messages"][:-keep]
        recent = session["messages"][-keep:]
        if to_archive:
            session["summary"] = await summarize_history(
                client, session["summary"], to_archive, game["name"]
            )
            session["messages"] = recent
            save_session(req.session_id)

    # 构建发送给模型的消息列表
    messages = [{"role": "system", "content": game["prompt"]}]

    if session.get("summary"):
        messages.append({
            "role": "system",
            "content": f"【前情提要】以下是之前发生过的剧情，请在此基础上继续：\n{session['summary']}",
        })

    messages.extend(session["messages"])

    # 末尾重述核心铁律
    core_rules = game.get("core_rules")
    if core_rules:
        messages.append({
            "role": "system",
            "content": (
                "【请始终牢记并严格遵守以下核心设定与规则，不要偏离人设和世界观】\n"
                f"{core_rules}"
            ),
        })

    # 创作自由度声明
    messages.append({"role": "system", "content": CREATIVE_FREEDOM_PROMPT})

    # XML 输出格式约束
    messages.append({"role": "system", "content": XML_FORMAT_PROMPT})

    async def generate():
        assistant_content = ""
        try:
            stream = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                stream=True,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    assistant_content += content
                    yield f"data: {content}\n\n"

            # 流结束，清理并校验
            cleaned = assistant_content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

            # 剥离 <scene> 之前的前导文字
            idx = cleaned.find("<scene")
            if idx < 0:
                idx = cleaned.find("<Scene")
            if idx > 0:
                cleaned = cleaned[idx:].strip()

            # XML 校验
            is_valid_xml = False
            if cleaned.startswith("<scene") or cleaned.startswith("<Scene"):
                try:
                    ET.fromstring(cleaned)
                    is_valid_xml = True
                except ET.ParseError:
                    is_valid_xml = False

            # 保存到历史
            session["messages"].append({"role": "assistant", "content": assistant_content})
            save_session(req.session_id)

            if is_valid_xml:
                yield "data: [FORMAT:XML]\n\n"
            else:
                yield "data: [FORMAT:MARKDOWN]\n\n"
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            if assistant_content:
                session["messages"].append(
                    {"role": "assistant", "content": assistant_content}
                )
            save_session(req.session_id)
            raise
        except Exception as e:
            if assistant_content:
                session["messages"].append(
                    {"role": "assistant", "content": assistant_content}
                )
            save_session(req.session_id)
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/random-avatar")
async def random_avatar():
    """返回一张随机头像的访问 URL"""
    name = pick_random_avatar()
    return {"avatar": f"/api/avatars/{name}" if name else None}


@app.post("/api/reset")
async def reset_session(session_id: str, game_id: str):
    """重置某个会话的对话历史"""
    if session_id in sessions:
        sessions[session_id]["messages"] = []
        save_session(session_id)
    return {"status": "ok"}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除一个存档"""
    delete_session_from_db(session_id)
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

    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "只支持 .docx 格式的文件哦~")

    GAMES_DIR.mkdir(parents=True, exist_ok=True)

    save_path = GAMES_DIR / file.filename
    content = await file.read()

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "文件太大了，最大支持 10MB")

    # 验证 docx 有效性
    try:
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        if not paragraphs:
            raise HTTPException(400, "这个文件里没有文字内容哦")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "无法识别这个文件，请确认是 .docx 格式")

    with open(save_path, "wb") as f:
        f.write(content)

    name = save_path.stem.lstrip("0123456789.").strip()
    if not name:
        name = save_path.stem

    load_games()
    return {"status": "ok", "name": name, "file": file.filename}


@app.delete("/api/games/{game_id}")
async def delete_game(game_id: str):
    """删除一个游戏"""
    game = games_cache.get(game_id)
    if not game:
        raise HTTPException(404, "游戏不存在")

    file_path = GAMES_DIR / game["file"]
    if file_path.exists():
        file_path.unlink()

    load_games()
    return {"status": "ok"}


# ============================================================
# 静态文件 & 前端
# ============================================================

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """返回前端页面"""
    index_path = Path(__file__).parent / "index.html"
    if index_path.exists():
        return HTMLResponse(
            index_path.read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    return HTMLResponse("<h1>AI文游游戏厅</h1><p>index.html 不存在</p>")


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    import uvicorn
    print(f"🎮 AI文游游戏厅启动中...")
    print(f"📍 访问地址: http://localhost:{PORT}")
    print(f"📂 游戏目录: {GAMES_DIR.absolute()}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
