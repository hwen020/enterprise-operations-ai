FROM python:3.12-slim
ENV HOST=0.0.0.0 PORT=8790 DATABASE_PATH=/app/var/demo.sqlite3 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 sandbox && mkdir -p /app/var && chown -R 10001:10001 /app
COPY --chown=10001:10001 operations ./operations
COPY --chown=10001:10001 migrations ./migrations
COPY --chown=10001:10001 web ./web
COPY --chown=10001:10001 assets ./assets
COPY --chown=10001:10001 fixtures ./fixtures
COPY --chown=10001:10001 server.py LICENSE ./
USER 10001
EXPOSE 8790
CMD ["python", "-B", "server.py"]
