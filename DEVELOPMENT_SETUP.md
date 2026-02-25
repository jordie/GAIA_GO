# GAIA_GO Development Setup Guide

Welcome to GAIA_GO! This guide will help you set up a complete development environment for working on the project.

## ⚡ Quick Start (5 minutes)

### Prerequisites
Check that you have these installed:
- Python 3.10+: `python3 --version`
- Go 1.23+: `go version`
- Git: `git --version`

### Setup Steps

```bash
# 1. Clone repository (if not already done)
cd ~/Desktop/gitrepo/pyWork/GAIA_GO

# 2. Run setup command
make setup

# 3. Start development servers
make dev

# 4. Access dashboard
# Open http://localhost:8080 in your browser
```

That's it! You're ready to develop.

## 📋 What Gets Set Up

Running `make setup` does:
1. Creates Python virtual environment
2. Installs all dependencies (production + development)
3. Initializes development database
4. Sets up pre-commit hooks for code quality

## 🚀 Development Workflow

### Starting Work

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Start development servers
make dev
```

This starts:
- **Flask API**: http://localhost:8080
- **Go Services**: http://localhost:9000
- **Hot reload**: Code changes automatically reload

### Making Changes

```bash
# Edit Python files in src/ or app.py
# Edit Go files in architect-go/
# Changes automatically reload!

# Run tests while developing
make test-unit

# Format code before committing
make format

# Check for lint errors
make lint
```

### Before Committing

```bash
# Run full test suite
make test-all

# Format code
make format

# Commit changes
git add .
git commit -m "feat: your feature description"
git push origin feature/your-feature-name
```

## 📚 Common Commands

### Testing

```bash
make test-unit           # Unit tests only (fastest - 2 min)
make test-integration    # Integration tests (5-10 min)
make test-e2e           # End-to-end tests (10-15 min)
make test-all           # All tests with coverage (20 min)
make test-watch         # Continuous test mode (re-run on file change)
```

### Code Quality

```bash
make format             # Auto-format all code
make lint               # Run linters
make clean-cache        # Clean Python cache files
```

### Database

```bash
make db-reset           # Clear and reinitialize database
make db-migrate         # Run pending migrations
```

### Development

```bash
make dev                # Start development servers
make dev-stop           # Stop development servers
make health-check       # Check all services are running
make verify             # Verify environment setup
```

### Cleanup

```bash
make clean              # Clean all build artifacts
make clean-cache        # Clean Python cache only
```

## 🔍 Verification

After setup, verify everything works:

```bash
make verify
```

This checks:
- Python installation
- Virtual environment
- Go installation
- Dependencies
- Database
- Required files

## 🐛 Debugging

### Python Debugging with VS Code

1. Set a breakpoint by clicking on a line number
2. Go to Debug panel (Ctrl+Shift+D on Linux/Windows, Cmd+Shift+D on Mac)
3. Select "Python: Flask Debug"
4. Press F5 (or click Start)
5. Your breakpoint will be hit when that code runs
6. Use the Debug toolbar to step through code

### Go Debugging with VS Code

1. Set a breakpoint in Go code
2. Go to Debug panel (Ctrl+Shift+D)
3. Select "Go: Architect Server"
4. Press F5
5. Step through the Go code

### Command-Line Debugging

```bash
# Python: Drop into debugger
python -m ipdb -c "c" app.py

# Check logs in real-time
tail -f logs/dev.log | grep -i error

# Database inspection
sqlite3 data/architect_dev.db
sqlite> .schema projects
sqlite> SELECT * FROM projects LIMIT 5;
```

## 📦 Managing Dependencies

### Add Python Package

```bash
source venv/bin/activate
pip install <package-name>
pip freeze > requirements.txt
```

### Add Development-Only Package

```bash
source venv/bin/activate
pip install <package-name>
pip freeze > requirements-dev.txt
```

### Add Go Package

```bash
cd architect-go
go get github.com/user/package
go mod tidy
```

### Update All Dependencies

```bash
# Python
source venv/bin/activate
pip install --upgrade -r requirements.txt
pip install --upgrade -r requirements-dev.txt

# Go
cd architect-go
go get -u ./...
go mod tidy
```

## 🔧 Troubleshooting

### Port Already in Use

```bash
# Find what's using the port
lsof -i :8080

# Kill the process
kill -9 <PID>
```

### Virtual Environment Issues

```bash
# Remove and recreate
rm -rf venv
make setup
```

### Database Locked

```bash
# Remove lock file and reset
rm -f data/*.db-journal
make db-reset
```

### Import Errors

```bash
# Reinstall dependencies
source venv/bin/activate
pip install -r requirements.txt --force-reinstall
```

### Test Failures

```bash
# Reset test database
make db-reset

# Run specific test with verbose output
python -m pytest tests/unit/test_api.py::test_login -vv -s

# Run with capture disabled to see print statements
pytest tests/ -s
```

### Go Build Issues

```bash
cd architect-go
go clean
go mod tidy
go build -o bin/server ./cmd/server
```

## 📖 Project Structure

```
GAIA_GO/
├── app.py                  # Flask application entry point
├── requirements.txt        # Production dependencies
├── requirements-dev.txt    # Development dependencies
├── Makefile               # Development commands
├── .venv_setup.sh         # Virtual environment setup
│
├── src/                   # Python source code
│   ├── services/          # Business logic
│   ├── routes/            # API routes
│   ├── models/            # Database models
│   └── utils/             # Utilities
│
├── architect-go/          # Go microservices
│   ├── cmd/               # Executable entry points
│   ├── internal/          # Internal packages
│   ├── pkg/               # Public packages
│   └── go.mod             # Go dependencies
│
├── tests/                 # Test suite
│   ├── unit/              # Unit tests
│   ├── integration/        # Integration tests
│   ├── e2e/               # End-to-end tests
│   ├── fixtures/          # Test data and factories
│   └── conftest.py        # Pytest configuration
│
├── migrations/            # Database migrations
├── data/                  # Data files (git-ignored)
│   ├── architect_dev.db   # Development database
│   └── test.db           # Test database
│
├── docs/                  # Documentation
├── scripts/               # Utility scripts
│   ├── verify_setup.sh    # Verify environment
│   └── health_check.sh    # Check service health
│
└── .vscode/              # VS Code configuration
    ├── settings.json      # Editor settings
    └── launch.json        # Debug configurations
```

## 🎓 Learning Resources

### Python/Flask
- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [Pytest Testing](https://docs.pytest.org/)

### Go
- [Go Documentation](https://golang.org/doc/)
- [Gin Web Framework](https://gin-gonic.com/)
- [Go Testing](https://golang.org/pkg/testing/)

### Development Tools
- [VS Code Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
- [VS Code Go](https://marketplace.visualstudio.com/items?itemName=golang.go)
- [Git & GitHub](https://guides.github.com/)

## 💬 Getting Help

### Check Logs
```bash
tail -f logs/dev.log
```

### Ask Team
- Check existing GitHub issues
- Ask in team Slack channel
- Create a new issue with details

### Debug Print Statements
```python
# Python
print(f"Debug: {variable}")
import json; print(json.dumps(data, indent=2))

# Go
log.Printf("Debug: %+v\n", variable)
```

## ✅ Verification Checklist

After setup, verify:

- [ ] Python 3.10+ installed
- [ ] Virtual environment created
- [ ] All dependencies installed (`pip list | grep flask`)
- [ ] Go 1.23+ installed
- [ ] Git repository cloned
- [ ] Database initialized
- [ ] `make dev` starts without errors
- [ ] Can access http://localhost:8080
- [ ] `make test-unit` passes
- [ ] Pre-commit hooks installed

## 🎉 Ready to Code!

You're all set up! Start with:

```bash
make dev
```

Then open http://localhost:8080 and start exploring the codebase!

Happy coding! 🚀
