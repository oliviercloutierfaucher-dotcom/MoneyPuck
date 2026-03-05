FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PREVIEW_HOST=0.0.0.0 \
    PREVIEW_PORT=8080

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN adduser --disabled-password --gecos '' appuser
RUN mkdir -p /home/appuser/.moneypuck && chown -R appuser:appuser /home/appuser/.moneypuck
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/')" || exit 1

CMD ["python", "-m", "app.web.web_preview"]
