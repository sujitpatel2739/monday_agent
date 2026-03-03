FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# Copy frontend into same directory so Flask can serve it
COPY frontend/index.html .

# Confirm everything is in place
RUN ls -la /app/

EXPOSE 8000

CMD gunicorn main:app --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120
