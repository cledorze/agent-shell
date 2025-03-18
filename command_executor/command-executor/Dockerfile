FROM rust:1.75.0-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Cargo.toml and Cargo.lock
COPY Cargo.toml ./
# If you have a Cargo.lock file, copy it too
# COPY Cargo.lock ./

# Create placeholder source file to cache dependencies
RUN mkdir -p src && \
    echo "fn main() {println!(\"Hello, World!\");}" > src/main.rs

# Build dependencies
RUN cargo build --release

# Remove the placeholder source
RUN rm -f src/main.rs

# Copy the actual source code
COPY . .

# Build the application
RUN cargo build --release

# Expose the port
EXPOSE 8084

# Run the application
CMD ["./target/release/command_executor"]
