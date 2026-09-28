FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY worker.py .
RUN useradd -u 10001 -m appuser
USER 10001
CMD ["python", "-u", "worker.py"]
