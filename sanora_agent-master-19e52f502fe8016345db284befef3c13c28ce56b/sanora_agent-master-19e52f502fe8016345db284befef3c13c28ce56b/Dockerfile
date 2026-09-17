FROM python:3.12-slim

# 设置工作目录
WORKDIR /app


# ========== 关键：彻底清理所有 apt 源配置 ==========
RUN rm -f /etc/apt/sources.list && \
    rm -f /etc/apt/sources.list.d/*.list && \
    rm -f /etc/apt/sources.list.d/*.sources

# ========== 重新创建纯净的 bookworm 源（阿里云）==========
RUN echo "deb https://mirrors.aliyun.com/debian trixie main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian-security trixie-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian trixie-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# ========== 清理缓存，防止旧元数据干扰 ==========
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/*
    
# Set working directory
WORKDIR /app

# Configure pip to use Chinese mirror
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set install.trusted-host mirrors.aliyun.com

# Install system dependencies, Node.js and fonts used by Huashu/Chromium
RUN apt-get update && apt-get install -y \
    gcc \
    nodejs \
    npm \
    fonts-noto-cjk \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install the pinned Huashu Node dependencies and Playwright Chromium.
WORKDIR /app/src/deepagent/sheld/skills/huashu-design
RUN npm ci --omit=dev && \
    npx playwright install --with-deps chromium && \
    node scripts/smoke_test.mjs

WORKDIR /app

# Expose port
EXPOSE 8000
