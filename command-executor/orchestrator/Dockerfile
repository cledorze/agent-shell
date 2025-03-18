FROM golang:1.19-bullseye

WORKDIR /app

# Copy go.mod and go.sum files
COPY go.mod ./
COPY go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN go build -o orchestrator ./cmd/orchestrator

# Expose the port
EXPOSE 8081

# Run the application
CMD ["./orchestrator"]
