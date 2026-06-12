"""
数据库模块 — SQLite 会话持久化
"""

import json
import sqlite3

from config import DB_PATH


# 内存会话缓存: session_id -> {game_id, messages, summary, avatar}
sessions: dict = {}


def init_db():
    """初始化数据库，建表（若不存在）"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                game_id    TEXT,
                messages   TEXT,
                summary    TEXT,
                avatar     TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # 兼容老库：缺失的列按需补加
        cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "summary" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN summary TEXT")
        if "avatar" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN avatar TEXT")
        conn.commit()
    finally:
        conn.close()


def load_sessions_from_db():
    """启动时把所有会话从数据库读回内存"""
    global sessions
    sessions.clear()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT session_id, game_id, messages, summary, avatar FROM sessions"
        ).fetchall()
        for session_id, game_id, messages_json, summary, avatar in rows:
            try:
                messages = json.loads(messages_json) if messages_json else []
            except (json.JSONDecodeError, TypeError):
                messages = []
            sessions[session_id] = {
                "game_id": game_id,
                "messages": messages,
                "summary": summary or "",
                "avatar": avatar or None,
            }
    finally:
        conn.close()
    print(f"💾 已从数据库恢复 {len(sessions)} 个会话")


def save_session(session_id: str):
    """把单个会话的当前状态写回数据库（UPSERT）"""
    session = sessions.get(session_id)
    if session is None:
        return
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            """
            INSERT INTO sessions (session_id, game_id, messages, summary, avatar, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET
                game_id    = excluded.game_id,
                messages   = excluded.messages,
                summary    = excluded.summary,
                avatar     = excluded.avatar,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                session_id,
                session["game_id"],
                json.dumps(session["messages"], ensure_ascii=False),
                session.get("summary", ""),
                session.get("avatar"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def delete_session_from_db(session_id: str):
    """从数据库中删除一个存档"""
    sessions.pop(session_id, None)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


def list_sessions_from_db() -> list:
    """从数据库查询所有存档（按最后活动时间倒序）"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT session_id, game_id, messages, avatar, updated_at "
            "FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
    finally:
        conn.close()
    return rows
