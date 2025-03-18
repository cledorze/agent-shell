FROM rust:1.70-slim as builder

WORKDIR /app

# Copy Cargo.toml and source code
COPY Cargo.toml .
COPY src ./src

# Build the application
RUN cargo build --release

FROM debian:bullseye-slim

WORKDIR /app

# Copy binary from builder stage
COPY --from=builder /app/target/release/command_executor /app/

# Expose port
EXPOSE 8084

# Run the binary
CMD ["/app/command_executor"]
