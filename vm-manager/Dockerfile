FROM golang:1.21-alpine AS builder

# Install build dependencies for libvirt
RUN apk add --no-cache gcc musl-dev pkgconfig libvirt-dev

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=1 GOOS=linux go build -a -o vm-manager ./cmd/manager

FROM alpine:3.18

# Install libvirt client and dependencies
RUN apk add --no-cache libvirt-client libvirt-dev openssh-client qemu-img ngrok

WORKDIR /app/
COPY --from=builder /app/vm-manager .

# Create directories for VM data
RUN mkdir -p /app/data/vms/vm-data /app/data/vms/vm-instances /app/data/templates

EXPOSE 8083
CMD ["./vm-manager"]
