FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码
COPY server.py index.html ./

# 创建游戏目录（运行时通过 volume 挂载）
RUN mkdir -p /app/games

EXPOSE 8080

CMD ["python", "server.py"]
