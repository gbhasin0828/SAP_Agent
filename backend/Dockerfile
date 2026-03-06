# Use Microsoft's official Playwright Python image
# It has Python + Chromium + all Linux dependencies pre-installed
FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

# Set working directory inside the container
WORKDIR /app

# Copy requirements first (Docker layer caching — reinstalls only if requirements change)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's Chromium browser
RUN playwright install chromium

# Copy all backend code into the container
COPY . .

# Tell the container to listen on port 8000
EXPOSE 8000

# Install Xvfb for virtual display (needed for Playwright on Linux)
RUN apt-get update && apt-get install -y xvfb && rm -rf /var/lib/apt/lists/*

# Start Xvfb virtual display then launch the app
CMD Xvfb :99 -screen 0 1280x720x24 & sleep 1 && DISPLAY=:99 uvicorn main:app --host 0.0.0.0 --port 8000
