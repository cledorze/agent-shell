FROM golang:1.19-bullseye

# Install libvirt development packages
RUN apt-get update && apt-get install -y \
    libvirt-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy go.mod and go.sum files
COPY go.mod ./
COPY go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN go build -o vm_manager ./cmd/vm_manager

# Expose the port
EXPOSE 8083

# Run the application
CMD ["./vm_manager"]
