FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including libvirt
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libvirt-clients \
    libvirt-daemon \
    libvirt-dev \
    python3-dev \
    pkg-config \
    qemu-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install libvirt Python bindings
RUN pip install --no-cache-dir libvirt-python

COPY . .

EXPOSE 8082
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8082"]
