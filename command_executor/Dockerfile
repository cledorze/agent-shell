FROM rust:1.75.0-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy Cargo.toml and source code
COPY . .

# Build the application
RUN cargo build --release

# Expose the port
EXPOSE 8084

# Run the application
CMD ["./target/release/command_executor"]
