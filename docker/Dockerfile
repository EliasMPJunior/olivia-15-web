FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY src/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home app
COPY --chown=app:app src/ ./
COPY --chown=app:app docker/entrypoint.sh /entrypoint.sh
RUN mkdir -p /data /app/staticfiles && chown -R app:app /data /app/staticfiles && chmod +x /entrypoint.sh
USER app
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
