# Минимальный Dockerfile для мгновенного деплоя PassiveNFT Bot
FROM python:3.14-slim

# Установка рабочей директории
WORKDIR /workspace

# Только curl для webhook (минимум системных зависимостей)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование файла зависимостей Python
COPY requirements.txt .

# Установка Python зависимостей (без компиляции)
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всех файлов приложения
COPY . .

# Запуск приложения
CMD ["python", "bot_deploy.py"]
