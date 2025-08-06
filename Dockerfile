FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей для Postgres
RUN apt-get update && apt-get install -y libpq-dev gcc

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем проект
COPY . .

CMD ["python", "bot.py"]