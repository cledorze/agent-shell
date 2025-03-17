FROM rust:1.75 as builder

WORKDIR /app

COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo 'fn main() { println!("Placeholder"); }' > src/main.rs
RUN cargo build --release
RUN rm -f target/release/deps/command_executor*

COPY . .
RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    openssl \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/target/release/command-executor .

EXPOSE 8085
CMD ["./command-executor"]
