FROM golang:1.19-bullseye as builder

WORKDIR /app
COPY . .
RUN go build -o orchestrator ./cmd/orchestrator

FROM debian:bullseye-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/orchestrator /app/

EXPOSE 8081
CMD ["./orchestrator"]
