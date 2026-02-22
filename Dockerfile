FROM python:3.10-slim

# ── System deps for headless OpenCASCADE (libGL.so.1) ──────────────
# MUST be installed BEFORE pip install to prevent the fatal crash.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1-mesa-glx \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ── Python deps ────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────
COPY . .

# ── Cloud Run expects port 8080 ───────────────────────────────────
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
