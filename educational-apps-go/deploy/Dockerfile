# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache gcc musl-dev sqlite-dev

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the unified app
RUN CGO_ENABLED=1 GOOS=linux go build -a -installsuffix cgo -o unified-app ./cmd/unified

# Runtime stage
FROM alpine:latest

WORKDIR /app

# Install runtime dependencies
RUN apk --no-cache add ca-certificates

# Copy binary from builder
COPY --from=builder /app/unified-app .

# Copy migrations
COPY migrations/ ./migrations/

# Copy web templates and static files
COPY web/templates/ ./web/templates/
COPY web/static/ ./web/static/

# Create .env from .env.example if it doesn't exist
COPY .env.example .env

EXPOSE 8080

CMD ["./unified-app"]
