FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    IN_DOCKER=true

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY telegram_listener.py get_chat_ids.py ./

CMD ["python", "telegram_listener.py"]

