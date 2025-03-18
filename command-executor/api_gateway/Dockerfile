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
RUN go build -o api_gateway ./cmd/api

# Expose the port
EXPOSE 8080

# Run the application
CMD ["./api_gateway"]
