.PHONY: all app run install history clean build test help

# Default target
all: app

# Run the application (English by default)
app:
	@echo "Starting ttyping (English)..."
	uv run ttyping

# Run the application (alias for app)
run: app

# Run tests
test:
	@echo "Running tests..."
	uv run pytest

# Install the application as a tool
install:
	@echo "Installing ttyping..."
	uv tool install .

# View history
history:
	@echo "Viewing history..."
	uv run ttyping history

# Clean build artifacts
clean:
	@echo "Cleaning up..."
	rm -rf dist build *.egg-info .pytest_cache .mypy_cache __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} +

# Build the package
build:
	@echo "Building package..."
	uv build

# Help command to display available targets
help:
	@echo "Available commands:"
	@echo "  make app      - Run the typing application (English)"
	@echo "  make run      - Alias for make app"
	@echo "  make test     - Run tests"
	@echo "  make install  - Install the application as a tool"
	@echo "  make history  - View typing history"
	@echo "  make clean    - Remove build artifacts and cache"
	@echo "  make build    - Build the package"
