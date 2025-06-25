# Makefile for Dockerized Labeling App

# If DATA_DIR is not specified, default to a './data' directory in the project folder.
# This allows running 'make run' without arguments for simple cases.
DATA_DIR ?= ./data

# Export the variable so it's available to docker compose.
export DATA_DIR

# Use .PHONY to prevent conflicts with files of the same name.
.PHONY: help run down build

# --- Main Commands ---

default: help

help:
	@echo ""
	@echo "Usage:"
	@echo "  make run [DATA_DIR=/path/to/your/data]   - Start the application."
	@echo "  make down                                - Stop the application and remove containers."
	@echo "  make build                               - Rebuild the Docker image."
	@echo ""
	@echo "Example:"
	@echo "  make run DATA_DIR=/Users/myname/Pictures/cat_dataset"
	@echo "  make run DATA_DIR=D:/Photos/2025_project"
	@echo ""

run:
	@echo "Starting application..."
	@echo "Host directory to be mounted: '$(DATA_DIR)'"
	@# Create the host directory if it doesn't exist to prevent Docker from creating a root-owned directory.
	@mkdir -p "$(DATA_DIR)"
	@docker compose up --build -d
	@echo ""
	@echo "----------------------------------------------------"
	@echo "  Application has started!"
	@echo ""
	@echo "  Please open the following URL in your browser:"
	@echo "  => http://localhost:8501"
	@echo "----------------------------------------------------"
	@echo ""

down:
	@echo "Stopping application..."
	@docker compose down

build:
	@echo "Building Docker image..."
	@docker compose build

