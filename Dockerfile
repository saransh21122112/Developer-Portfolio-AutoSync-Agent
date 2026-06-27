FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run the agent in polling daemon loop
CMD ["python", "main.py", "--daemon"]
