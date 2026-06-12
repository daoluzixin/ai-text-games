"""
游戏管理模块 — 加载 docx、头像分配、辅助提取
"""

import re
import hashlib
import random
from pathlib import Path
from typing import Optional

from docx import Document

from config import GAMES_DIR, AVATARS_DIR, CORE_RULES_MAX_CHARS


# 游戏缓存: game_id -> {name, prompt, core_rules, summary, file, avatar}
games_cache: dict = {}


# ============================================================
# 头像
# ============================================================

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


def pick_random_avatar() -> Optional[str]:
    """从 avatars/ 目录随机选一张头像文件名，无头像时返回 None"""
    avatars = get_avatar_list()
    return random.choice(avatars) if avatars else None


# ============================================================
# 核心铁律 & 简介提取
# ============================================================

def extract_core_rules(prompt: str, docx_file: Path) -> str:
    """提取一个游戏的「核心铁律」，用于对话末尾重述，防止 AI 长对话后跑偏。

    优先级：
      1. 同名 .rules.txt（或 .rules）文件 — 作者手动指定，最精准
      2. 退化方案：取 docx 开头若干段落，累积到 CORE_RULES_MAX_CHARS 为止
    """
    # 1. 手动规则文件覆盖
    for suffix in (".rules.txt", ".rules"):
        rules_path = docx_file.with_suffix(suffix)
        if rules_path.exists():
            try:
                text = rules_path.read_text(encoding="utf-8").strip()
                if text:
                    return text
            except Exception:
                pass

    # 2. 从 docx 开头累积段落
    rules_parts = []
    total = 0
    for line in prompt.split("\n"):
        line = line.strip()
        if not line:
            continue
        rules_parts.append(line)
        total += len(line)
        if total >= CORE_RULES_MAX_CHARS:
            break
    return "\n".join(rules_parts)


def extract_summary(prompt: str, max_len: int = 50) -> str:
    """从 prompt 中提取一句话简介。

    策略：跳过免责声明、规则/设定行，取第一段看起来像「故事背景描述」的句子。
    """
    skip_prefixes = ("#", "【", "你是", "你扮演", "你需要", "你要", "规则", "设定",
                     "系统", "System", "system", "---", "===", "***",
                     "指令", "注意", "免责", "声明", "警告", "提示：",
                     "以下", "本游戏", "本文", "重要", "必看", "玩前",
                     "游戏指令", "通用指令", "开始游戏")
    skip_keywords = ("纯属虚构", "与现实无关", "请勿", "健康游玩", "休闲娱乐",
                     "免责", "仅供娱乐", "如有雷同", "AI实际生成", "不代表",
                     "18岁", "未成年", "违法", "违规",
                     "必看", "此段不复制", "复制到备忘录", "不要复制",
                     "使用说明", "使用方法", "食用方法", "食用说明",
                     "指令", "通用指令", "游戏指令")

    # 匹配章节标题行
    heading_re = re.compile(
        r'^([一二三四五六七八九十]+、|[0-9]+[.、）)]|\d+\s|第.{1,3}[章节部分]|[A-Z]\.|Part\s)'
    )

    for line in prompt.split("\n"):
        line = line.strip()
        if not line:
            continue
        if any(line.startswith(p) for p in skip_prefixes):
            continue
        if any(kw in line for kw in skip_keywords):
            continue
        if heading_re.match(line):
            continue
        if len(line) < 6:
            continue
        # 找到了一行合适的描述
        if len(line) > max_len:
            return line[:max_len] + "…"
        return line
    # 兜底
    flat = prompt.replace("\n", " ").strip()
    if len(flat) > max_len:
        return flat[:max_len] + "…"
    return flat


# ============================================================
# 游戏加载
# ============================================================

def load_games():
    """扫描 games/ 目录，加载所有 docx 文件"""
    global games_cache
    games_cache.clear()

    if not GAMES_DIR.exists():
        GAMES_DIR.mkdir(parents=True, exist_ok=True)
        return

    for docx_file in sorted(GAMES_DIR.glob("*.docx")):
        try:
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
                    "core_rules": extract_core_rules(prompt, docx_file),
                    "summary": extract_summary(prompt),
                    "file": docx_file.name,
                    "avatar": assign_avatar(game_id),
                }
        except Exception as e:
            print(f"⚠️  加载失败 {docx_file.name}: {e}")

    print(f"📂 已加载 {len(games_cache)} 个游戏")
