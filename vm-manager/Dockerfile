FROM golang:1.21-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o vm-manager ./cmd/manager

FROM alpine:3.18

RUN apk --no-cache add ca-certificates libvirt-client

WORKDIR /app/
COPY --from=builder /app/vm-manager .

EXPOSE 8083
CMD ["./vm-manager"]
