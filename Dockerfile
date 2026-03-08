FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN adduser --disabled-password --gecos '' appuser
RUN mkdir -p /home/appuser/.moneypuck && chown -R appuser:appuser /home/appuser/.moneypuck
RUN mkdir -p /data && chown -R appuser:appuser /data
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/')" || exit 1

CMD uvicorn app.web.app:app --host 0.0.0.0 --port ${PORT:-8080}
