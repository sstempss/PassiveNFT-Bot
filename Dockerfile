# 🚀 БЫСТРЫЙ Dockerfile для PassiveNFT Bot
FROM python:3.11-slim

# Установка только необходимых системных пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование файлов бота
COPY . .

# Переменные окружения
ENV PYTHONPATH=/workspace
ENV PORT=8000

# Запуск
CMD ["python", "app.py"]
