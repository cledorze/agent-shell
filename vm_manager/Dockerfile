FROM golang:1.19-alpine AS builder

WORKDIR /app

# Copy go.mod
COPY go.mod ./

# Copy source code
COPY cmd/ ./cmd/

# Download dependencies
RUN go mod download

# Build the application (statically linked)
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o vm_manager ./cmd/vm_manager

FROM alpine:3.14

WORKDIR /app

# Copy binary from builder stage
COPY --from=builder /app/vm_manager /app/

# Expose port
EXPOSE 8083

# Run the binary
CMD ["/app/vm_manager"]
