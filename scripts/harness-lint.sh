#!/bin/bash
# ============================================================
# AI文游游戏厅 - Harness Lint 脚本
# ============================================================
# 用途：自动化守卫，检查架构约束 + 文档完整性 + 目录结构
# 用法：bash scripts/harness-lint.sh
# 要求：0 FAIL 才允许 push
# ============================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

check() {
    local desc="$1"
    local result="$2"
    if [ "$result" = "0" ]; then
        echo "  ✅ PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "  ❌ FAIL: $desc"
        FAIL=$((FAIL + 1))
    fi
}

echo "🔍 Harness Lint — AI文游游戏厅"
echo "=================================="
echo ""

# ──────────────────────────────────────────────
# 1. 文档完整性检查
# ──────────────────────────────────────────────
echo "📄 [文档完整性]"

test -f "AGENTS.md"
check "AGENTS.md 存在" "$?"

test -f "docs/agents/目元信息.md"
check "docs/agents/目元信息.md 存在" "$?"

test -f "docs/agents/核心架构.md"
check "docs/agents/核心架构.md 存在" "$?"

test -f "docs/agents/工程约束.md"
check "docs/agents/工程约束.md 存在" "$?"

test -f "docs/agents/自反馈工作流.md"
check "docs/agents/自反馈工作流.md 存在" "$?"

test -f "docs/exec-plans/README.md"
check "docs/exec-plans/README.md 存在" "$?"

echo ""

# ──────────────────────────────────────────────
# 2. 目录结构检查
# ──────────────────────────────────────────────
echo "📁 [目录结构]"

test -d "docs/exec-plans/active"
check "docs/exec-plans/active/ 目录存在" "$?"

test -d "docs/exec-plans/completed"
check "docs/exec-plans/completed/ 目录存在" "$?"

test -d "docs/exec-plans/activeLog"
check "docs/exec-plans/activeLog/ 目录存在" "$?"

test -d "scripts"
check "scripts/ 目录存在" "$?"

test -d "avatars"
check "avatars/ 目录存在" "$?"

echo ""

# ──────────────────────────────────────────────
# 3. 架构约束检查
# ──────────────────────────────────────────────
echo "🏗️  [架构约束]"

# 后端必须是单文件
PYTHON_FILES=$(find . -maxdepth 1 -name "*.py" -not -name "__*" | wc -l | tr -d ' ')
if [ "$PYTHON_FILES" -le 1 ]; then
    check "后端保持单文件原则（当前 $PYTHON_FILES 个 .py）" "0"
else
    check "后端保持单文件原则（当前 $PYTHON_FILES 个 .py，超过 1 个）" "1"
fi

# .env 不在 git 跟踪中（检查 .gitignore 包含 .env）
if grep -q "^\.env$" .gitignore 2>/dev/null; then
    check ".gitignore 包含 .env" "0"
else
    check ".gitignore 包含 .env" "1"
fi

# sessions.db 不在 git 跟踪中
if grep -q "sessions.db" .gitignore 2>/dev/null; then
    check ".gitignore 包含 sessions.db" "0"
else
    check ".gitignore 包含 sessions.db" "1"
fi

# games/*.docx 不在 git 跟踪中
if grep -q "games/\*\.docx" .gitignore 2>/dev/null; then
    check ".gitignore 包含 games/*.docx" "0"
else
    check ".gitignore 包含 games/*.docx" "1"
fi

echo ""

# ──────────────────────────────────────────────
# 4. 代码基本检查
# ──────────────────────────────────────────────
echo "🐍 [代码检查]"

# server.py 存在且可被 Python 解析
if python3 -c "import ast; ast.parse(open('server.py').read())" 2>/dev/null; then
    check "server.py 语法正确" "0"
else
    check "server.py 语法正确" "1"
fi

# requirements.txt 存在且非空
if [ -s "requirements.txt" ]; then
    check "requirements.txt 存在且非空" "0"
else
    check "requirements.txt 存在且非空" "1"
fi

# index.html 存在
test -f "index.html"
check "index.html 存在" "$?"

echo ""

# ──────────────────────────────────────────────
# 5. 配置检查
# ──────────────────────────────────────────────
echo "⚙️  [配置检查]"

# .env.example 存在（给新开发者参考）
test -f ".env.example"
check ".env.example 模板存在" "$?"

# Dockerfile 存在
test -f "Dockerfile"
check "Dockerfile 存在" "$?"

echo ""

# ──────────────────────────────────────────────
# 汇总
# ──────────────────────────────────────────────
echo "=================================="
echo "📊 结果: $PASS PASS / $FAIL FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "❌ 存在 $FAIL 项检查未通过，请修复后再提交。"
    exit 1
else
    echo "✅ 全部通过！可以提交。"
    exit 0
fi
