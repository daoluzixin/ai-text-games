#!/bin/bash
# ============================================================
# AI文游游戏厅 - 一键部署脚本（云服务器用）
# ============================================================
# 用法: 
#   1. 把整个 ai-text-games/ 目录传到服务器
#   2. 配置 .env 文件
#   3. 运行: bash deploy.sh
# ============================================================

set -e

echo "🎮 AI文游游戏厅 - 部署中..."
echo "=================================="

# 检查 .env
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件，正在从模板创建..."
    cp .env.example .env
    echo "❗ 请编辑 .env 文件填入你的 API_KEY"
    echo "   vim .env"
    exit 1
fi

# 检查 games 目录
if [ ! -d games ] || [ -z "$(ls -A games/*.docx 2>/dev/null)" ]; then
    echo "⚠️  games/ 目录为空，请放入 .docx 游戏文件"
    mkdir -p games
    echo "   示例: scp ~/Downloads/太后模拟器.docx server:~/ai-text-games/games/"
    exit 1
fi

GAME_COUNT=$(ls games/*.docx 2>/dev/null | wc -l)
echo "📂 检测到 ${GAME_COUNT} 个游戏文件"

# 检查 Docker
if command -v docker &> /dev/null; then
    echo "🐳 使用 Docker 部署..."
    docker compose up -d --build
    echo ""
    echo "✅ 部署成功!"
    echo "🌐 访问地址: http://$(hostname -I | awk '{print $1}'):8080"
    echo ""
    echo "📝 常用命令:"
    echo "   查看日志:  docker compose logs -f"
    echo "   停止服务:  docker compose down"
    echo "   重启服务:  docker compose restart"
    echo "   添加游戏:  往 games/ 丢 docx 文件，无需重启"
else
    echo "📦 未检测到 Docker，使用直接部署..."
    
    # 创建虚拟环境
    if [ ! -d .venv ]; then
        python3 -m venv .venv
    fi
    source .venv/bin/activate
    
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    
    echo ""
    echo "✅ 依赖安装完成!"
    echo "🚀 启动服务..."
    echo "   前台运行: python server.py"
    echo "   后台运行: nohup python server.py > server.log 2>&1 &"
    echo ""
    
    # 直接启动
    python server.py
fi
