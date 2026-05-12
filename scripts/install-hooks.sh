#!/usr/bin/env bash
# Pre-commit hook installer for Filum project

set -e

echo "Installing pre-commit hooks..."

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit..."
    if command -v pip &> /dev/null; then
        pip install pre-commit
    elif command -v uv &> /dev/null; then
        uv tool install pre-commit
    else
        echo "Error: Neither pip nor uv found. Please install pre-commit manually."
        exit 1
    fi
fi

# Install hooks
pre-commit install --config .pre-commit-config.yaml

echo "Pre-commit hooks installed successfully!"
echo ""
echo "Available hooks:"
echo "  - trailing-whitespace"
echo "  - end-of-file-fixer"
echo "  - check-yaml"
echo "  - check-added-large-files"
echo "  - ruff (lint + format)"
echo "  - mypy (type checking)"
echo "  - eslint (frontend)"
echo "  - prettier (frontend)"
echo "  - dbt-compile (analytics)"
echo ""
echo "To run manually: pre-commit run --all-files"
echo "To skip hooks: git commit --no-verify"
