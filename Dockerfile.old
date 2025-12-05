# 🚀 ОПТИМИЗИРОВАННЫЙ Dockerfile для PassiveNFT Bot
# УБРАНЫ: build-essential, libpq-dev, perl - ЭКОНОМИТ 300MB+ и 10+ минут деплоя

FROM python:3.14-slim
WORKDIR /workspace

# УСТАНАВЛИВАЕМ ТОЛЬКО curl для webhook функциональности
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# КОПИРУЕМ requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# КОПИРУЕМ все файлы бота
COPY . .

# ЗАПУСКАЕМ бота
CMD ["python", "bot_deploy.py"]
