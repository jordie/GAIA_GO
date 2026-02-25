.PHONY: help build run test clean deps lint docker-up docker-down migrate

help:
	@echo "Educational Apps - Go Migration"
	@echo ""
	@echo "Available commands:"
	@echo "  make build          Build the unified app binary"
	@echo "  make run            Run the app locally"
	@echo "  make test           Run all tests"
	@echo "  make test-coverage  Run tests with coverage report"
	@echo "  make lint           Run linter"
	@echo "  make clean          Remove build artifacts"
	@echo "  make deps           Download dependencies"
	@echo "  make docker-up      Start Docker containers"
	@echo "  make docker-down    Stop Docker containers"
	@echo "  make docker-logs    View Docker logs"
	@echo "  make migrate        Run database migrations"
	@echo "  make dev            Run with hot reload (requires air)"

build:
	CGO_ENABLED=0 go build -o unified-app ./cmd/unified

run: build
	./unified-app

test:
	go test -v -race ./...

test-coverage:
	go test -v -race -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report generated: coverage.html"

lint:
	golangci-lint run ./...

clean:
	rm -f unified-app coverage.out coverage.html
	go clean

deps:
	go mod download
	go mod tidy

docker-up:
	docker-compose -f deploy/docker-compose.yml up -d

docker-down:
	docker-compose -f deploy/docker-compose.yml down

docker-logs:
	docker-compose -f deploy/docker-compose.yml logs -f app

docker-clean:
	docker-compose -f deploy/docker-compose.yml down -v

migrate:
	@echo "Running migrations..."
	psql -h localhost -U postgres -d educational_apps -f migrations/001_initial_schema.up.sql

dev:
	@command -v air >/dev/null 2>&1 || (echo "Installing air..." && go install github.com/cosmtrek/air@latest)
	air

fmt:
	go fmt ./...

.DEFAULT_GOAL := help
