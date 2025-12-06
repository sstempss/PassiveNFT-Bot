# 🚀 Professional Dockerfile для PassiveNFT Bot
# Оптимизировано для TimeWeb деплоя
FROM python:3.11-slim

# Установка минимальных системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Установка Python зависимостей сначала (для кэширования)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование файлов приложения
COPY . .

# Переменные окружения для TimeWeb
ENV PYTHONPATH=/app
ENV FLASK_ENV=production
ENV PORT=8000

# Экспорт порта
EXPOSE 8000

# Запуск через Flask wrapper (не напрямую через main)
CMD ["python", "app.py"]
