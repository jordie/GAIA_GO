# Multi-stage build for architect-go
# Stage 1: Build
FROM golang:1.21-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git ca-certificates tzdata

WORKDIR /build

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the binary
# CGO_ENABLED=0 ensures static linking (no libc dependency)
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-s -w -X main.Version=$(git describe --tags --always --dirty 2>/dev/null || echo 'dev')" \
    -o /build/server \
    ./cmd/main.go

# Stage 2: Runtime
FROM alpine:3.19

# Install runtime dependencies
RUN apk add --no-cache ca-certificates tzdata

# Create non-root user
RUN addgroup -g 1000 appuser && adduser -D -u 1000 -G appuser appuser

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/server /app/server

# Copy migrations (if they exist)
COPY --chown=appuser:appuser migrations/ /app/migrations/ 2>/dev/null || true

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8080/health || exit 1

# Expose port
EXPOSE 8080

# Run the server
CMD ["/app/server"]
