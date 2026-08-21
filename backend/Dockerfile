FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# Shell form (not exec-array) so ${PORT} is substituted at container start.
# Railway and Render inject their own PORT at runtime and route traffic to
# it — a hardcoded --port 8000 makes the app unreachable on those platforms
# whenever they assign a different port. Falls back to 8000 for local
# docker-compose, where PORT is unset.
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
