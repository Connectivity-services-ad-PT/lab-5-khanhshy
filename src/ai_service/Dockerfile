# syntax=docker/dockerfile:1.7

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /service

RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --home /service appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appgroup main.py .

USER appuser

EXPOSE 9000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9000/health', timeout=3).read()" || exit 1

CMD ["python", "main.py"]
