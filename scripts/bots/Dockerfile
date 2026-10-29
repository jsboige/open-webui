FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY channel_bot.py .

ENV PYTHONUNBUFFERED=1

CMD ["python", "channel_bot.py"]
