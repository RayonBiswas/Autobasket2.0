# AutoBasket API and worker. Same image, two commands: `api` (default) and `worker`.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && useradd --create-home --uid 10001 autobasket \
    && chown -R autobasket:autobasket /app
USER autobasket

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["api"]
