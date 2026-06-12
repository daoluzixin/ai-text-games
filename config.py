"""
配置模块 — 所有可调参数集中管理
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ======== AI API ========
API_KEY = os.getenv("API_KEY", "")
API_BASE_URL = os.getenv("API_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
MODEL_NAME = os.getenv("MODEL_NAME", "doubao-1-5-pro-256k-250115")

# ======== 生成参数 ========
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8192"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.9"))

# ======== 长上下文记忆 ========
SUMMARY_TRIGGER = int(os.getenv("SUMMARY_TRIGGER", "30"))
KEEP_RECENT_MESSAGES = int(os.getenv("KEEP_RECENT_MESSAGES", "12"))
CORE_RULES_MAX_CHARS = int(os.getenv("CORE_RULES_MAX_CHARS", "600"))

# ======== 路径 ========
GAMES_DIR = Path(os.getenv("GAMES_DIR", "./games"))
AVATARS_DIR = Path(os.getenv("AVATARS_DIR", "./avatars"))
DB_PATH = Path(os.getenv("DB_PATH", "./sessions.db"))

# ======== 服务 ========
PORT = int(os.getenv("PORT", "8080"))
