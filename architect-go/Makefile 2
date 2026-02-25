.PHONY: help build test lint docker-build docker-run docker-down k8s-staging k8s-prod clean

# Variables
BINARY_NAME=server
DOCKER_IMAGE=architect-go
DOCKER_TAG=latest
DOCKER_REGISTRY=ghcr.io
GO=go
GOLANGCI_LINT=golangci-lint

# Colors for output
RED=\033[0;31m
GREEN=\033[0;32m
YELLOW=\033[0;33m
BLUE=\033[0;34m
NC=\033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)Architect Go Makefile$(NC)"
	@echo "$(BLUE)=====================$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# Build targets
build: ## Build the application binary
	@echo "$(BLUE)Building $(BINARY_NAME)...$(NC)"
	CGO_ENABLED=0 $(GO) build -o $(BINARY_NAME) ./cmd/main.go
	@echo "$(GREEN)✓ Build complete: $(BINARY_NAME)$(NC)"

build-debug: ## Build with debug symbols
	@echo "$(BLUE)Building $(BINARY_NAME) with debug symbols...$(NC)"
	$(GO) build -o $(BINARY_NAME) ./cmd/main.go
	@echo "$(GREEN)✓ Debug build complete$(NC)"

# Testing targets
test: ## Run all tests
	@echo "$(BLUE)Running tests...$(NC)"
	$(GO) test ./... -v -race -coverprofile=coverage.out
	@echo "$(GREEN)✓ Tests complete$(NC)"

test-coverage: test ## Run tests and show coverage
	@echo "$(BLUE)Coverage report:$(NC)"
	$(GO) tool cover -html=coverage.out -o coverage.html
	@echo "$(GREEN)Coverage HTML generated: coverage.html$(NC)"

# Linting targets
lint: ## Run linter
	@echo "$(BLUE)Running linter...$(NC)"
	@command -v $(GOLANGCI_LINT) >/dev/null 2>&1 || { echo "$(RED)golangci-lint not found. Install: https://golangci-lint.run/usage/install/$(NC)"; exit 1; }
	$(GOLANGCI_LINT) run ./...
	@echo "$(GREEN)✓ Lint complete$(NC)"

fmt: ## Format code
	@echo "$(BLUE)Formatting code...$(NC)"
	$(GO) fmt ./...
	@echo "$(GREEN)✓ Format complete$(NC)"

vet: ## Run go vet
	@echo "$(BLUE)Running go vet...$(NC)"
	$(GO) vet ./...
	@echo "$(GREEN)✓ Vet complete$(NC)"

# Docker targets
docker-build: ## Build Docker image
	@echo "$(BLUE)Building Docker image: $(DOCKER_IMAGE):$(DOCKER_TAG)...$(NC)"
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .
	@echo "$(GREEN)✓ Docker image built$(NC)"

docker-build-release: ## Build and tag Docker image for release
	@echo "$(BLUE)Building Docker image for release...$(NC)"
	docker build -t $(DOCKER_IMAGE):latest .
	@echo "$(GREEN)✓ Docker image built$(NC)"

docker-run: docker-build ## Build and run Docker container with docker-compose
	@echo "$(BLUE)Starting Docker containers...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Containers started$(NC)"
	@echo "$(BLUE)Access the application:$(NC)"
	@echo "  - API: http://localhost:8080"
	@echo "  - Health: http://localhost:8080/health"
	@echo "  - Metrics: http://localhost:8080/metrics"
	@echo "  - Database: localhost:5432 (postgres://architect:architect-dev@localhost/architect)"

docker-run-monitoring: ## Start containers with monitoring (Prometheus)
	@echo "$(BLUE)Starting containers with Prometheus...$(NC)"
	docker-compose --profile monitoring up -d
	@echo "$(GREEN)✓ Containers started with monitoring$(NC)"
	@echo "$(BLUE)Access monitoring:$(NC)"
	@echo "  - Prometheus: http://localhost:9090"

docker-logs: ## View Docker logs
	@echo "$(BLUE)Showing Docker logs...$(NC)"
	docker-compose logs -f app

docker-down: ## Stop Docker containers
	@echo "$(BLUE)Stopping Docker containers...$(NC)"
	docker-compose down -v
	@echo "$(GREEN)✓ Containers stopped$(NC)"

docker-clean: docker-down ## Remove Docker containers and images
	@echo "$(BLUE)Removing Docker image...$(NC)"
	docker rmi $(DOCKER_IMAGE):$(DOCKER_TAG) 2>/dev/null || true
	@echo "$(GREEN)✓ Docker cleanup complete$(NC)"

docker-shell: ## Open shell in running container
	@docker-compose exec app sh

# Kubernetes targets
k8s-staging: ## Deploy to staging Kubernetes cluster
	@echo "$(BLUE)Deploying to staging cluster...$(NC)"
	@command -v kubectl >/dev/null 2>&1 || { echo "$(RED)kubectl not found$(NC)"; exit 1; }
	kubectl apply -k k8s/staging/
	@echo "$(GREEN)✓ Staging deployment complete$(NC)"

k8s-staging-status: ## Check staging deployment status
	@echo "$(BLUE)Staging deployment status:$(NC)"
	kubectl -n architect-staging get deployments -o wide
	kubectl -n architect-staging get pods -o wide
	kubectl -n architect-staging get services

k8s-staging-logs: ## View staging pod logs
	@kubectl -n architect-staging logs -f deployment/architect-go

k8s-prod: ## Deploy to production Kubernetes cluster
	@echo "$(YELLOW)WARNING: Deploying to PRODUCTION cluster$(NC)"
	@command -v kubectl >/dev/null 2>&1 || { echo "$(RED)kubectl not found$(NC)"; exit 1; }
	kubectl apply -k k8s/production/
	@echo "$(GREEN)✓ Production deployment complete$(NC)"

k8s-prod-status: ## Check production deployment status
	@echo "$(BLUE)Production deployment status:$(NC)"
	kubectl -n architect-production get deployments -o wide
	kubectl -n architect-production get pods -o wide
	kubectl -n architect-production get services

k8s-prod-logs: ## View production pod logs
	@kubectl -n architect-production logs -f deployment/architect-go

k8s-validate: ## Validate Kubernetes manifests
	@echo "$(BLUE)Validating Kubernetes manifests...$(NC)"
	kubectl apply --dry-run=client -k k8s/staging/
	kubectl apply --dry-run=client -k k8s/production/
	@echo "$(GREEN)✓ Manifests are valid$(NC)"

k8s-delete-staging: ## Delete staging deployment
	@echo "$(YELLOW)WARNING: Deleting staging deployment$(NC)"
	kubectl delete -k k8s/staging/ --ignore-not-found=true
	@echo "$(GREEN)✓ Staging deployment deleted$(NC)"

k8s-delete-prod: ## Delete production deployment
	@echo "$(RED)ERROR: This is a destructive operation. Use kubectl directly if needed.$(NC)"

# Development targets
run: build ## Build and run the application locally
	@echo "$(BLUE)Running $(BINARY_NAME)...$(NC)"
	./$(BINARY_NAME)

run-dev: build-debug ## Build with debug symbols and run
	./$(BINARY_NAME)

watch: ## Run with auto-reload on file changes
	@command -v air >/dev/null 2>&1 || { echo "$(RED)air not found. Install: go install github.com/cosmtrek/air@latest$(NC)"; exit 1; }
	air

# Clean targets
clean: ## Clean build artifacts
	@echo "$(BLUE)Cleaning...$(NC)"
	rm -f $(BINARY_NAME)
	rm -f coverage.out coverage.html
	$(GO) clean
	@echo "$(GREEN)✓ Clean complete$(NC)"

# Dependency management
deps: ## Download and verify dependencies
	@echo "$(BLUE)Downloading dependencies...$(NC)"
	$(GO) mod download
	$(GO) mod verify
	@echo "$(GREEN)✓ Dependencies verified$(NC)"

tidy: ## Tidy and verify dependencies
	@echo "$(BLUE)Tidying dependencies...$(NC)"
	$(GO) mod tidy
	@echo "$(GREEN)✓ Dependencies tidy complete$(NC)"

# Database targets
db-migrate: ## Run database migrations
	@echo "$(BLUE)Running database migrations...$(NC)"
	@echo "$(YELLOW)Note: Migrations run automatically on app startup$(NC)"
	docker-compose exec app ./server migrate

db-seed: ## Seed database with sample data
	@echo "$(BLUE)Seeding database...$(NC)"
	@echo "$(YELLOW)Not yet implemented$(NC)"

# CI/CD targets
ci: lint test build ## Run CI checks (lint, test, build)
	@echo "$(GREEN)✓ All CI checks passed$(NC)"

ci-docker: ci docker-build ## Run full CI including Docker build
	@echo "$(GREEN)✓ Full CI complete$(NC)"

# Utility targets
version: ## Show build version info
	@echo "$(BLUE)Build Information$(NC)"
	@echo "  Go Version: $$(go version)"
	@echo "  OS: $$(go env GOOS)"
	@echo "  Arch: $$(go env GOARCH)"
	@echo "  Binary: $(BINARY_NAME)"

.DEFAULT_GOAL := help
