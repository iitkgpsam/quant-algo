FROM python:3.12-slim
RUN pip install --no-cache-dir flask==3.1.* gunicorn==23.*
WORKDIR /app
COPY portal_app.py .
USER 1000:1000
CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "2", "--access-logfile", "-", "portal_app:create_app()"]
