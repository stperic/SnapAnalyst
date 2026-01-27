# Contributing to SnapAnalyst

Thank you for your interest in contributing to SnapAnalyst! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Code Style](#code-style)
- [AI-Assisted & Vibe-Coded Contributions](#ai-assisted--vibe-coded-contributions-)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment. Please be considerate and constructive in all interactions.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up the development environment (see below)
4. Create a branch for your changes
5. Make your changes and test them
6. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker and Docker Compose (optional, for containerized development)

### Local Setup

```bash
# Clone your fork
git clone https://github.com/stperic/SnapAnalyst.git
cd SnapAnalyst

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements/base.txt
pip install -r requirements/dev.txt

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Start PostgreSQL (if not using Docker)
# Ensure PostgreSQL is running on localhost:5432

# Initialize database
python -m src.database.init_database

# Run the application
chainlit run chainlit_app.py
```

### Docker Setup

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

## Making Changes

### Branch Naming

Use descriptive branch names:
- `feature/add-new-export-format`
- `fix/query-timeout-issue`
- `docs/update-api-reference`
- `refactor/simplify-etl-pipeline`

### Commit Messages

Follow conventional commit format:

```
type(scope): short description

Longer description if needed.

Co-Authored-By: Your Name <your.email@example.com>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

## Code Style

### Python Style

We use `ruff` for linting and formatting:

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Style Guidelines

- Use Python 3.10+ type hints (`list[str]` not `List[str]`, `X | None` not `Optional[X]`)
- Add `from __future__ import annotations` for forward references
- Keep functions focused and under 50 lines when possible
- Write docstrings for all public functions and classes
- Use meaningful variable names

### Project Structure

```
SnapAnalyst/
├── src/                 # Core application code
│   ├── api/            # FastAPI REST API
│   ├── core/           # Configuration, logging, prompts
│   ├── database/       # SQLAlchemy models, DDL extraction
│   ├── etl/            # ETL pipeline (reader, transformer, loader)
│   ├── services/       # Business logic services
│   └── utils/          # Utility functions
├── ui/                  # Chainlit UI layer
│   ├── handlers/       # Event and command handlers
│   └── services/       # UI-specific services
├── datasets/            # Multi-dataset configurations
├── tests/               # Test suite
│   ├── unit/           # Unit tests
│   └── integration/    # Integration tests
└── scripts/             # Utility scripts
```

## AI-Assisted & Vibe-Coded Contributions 🤖

We welcome contributions built with AI coding assistants! Code generated or assisted by Claude, Copilot, Cursor, or other AI tools is absolutely acceptable.

### AI Contribution Guidelines

**Please include in your PR:**

1. **Mark as AI-assisted** in the PR title or description
   - Example: `feat: add export formats [AI-assisted]`
   - Or note in description: "Generated with Claude/Copilot"

2. **Note the degree of testing**
   - Untested / Lightly tested / Fully tested
   - Include test results or coverage reports

3. **Include context if possible** (super helpful!)
   - Prompts or session logs
   - Design decisions made during generation
   - Areas that need review

4. **Confirm you understand the code**
   - Be ready to explain what the code does
   - Understand any trade-offs or limitations
   - Can debug or modify if issues arise

### Why We Love AI Contributions

- **Transparency**: Knowing code is AI-generated helps reviewers focus on logic and architecture
- **Speed**: AI can help implement features faster
- **Learning**: Great way to learn the codebase
- **Innovation**: AI often suggests creative solutions

AI PRs are first-class citizens here. We just want transparency so reviewers know what to look for and can provide better feedback.

## Testing

### Running Tests

```bash
# Run all unit tests
pytest tests/unit/

# Run with coverage
pytest tests/unit/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_transformer.py -v

# Run integration tests (requires database)
pytest tests/integration/
```

### Writing Tests

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Use descriptive test names: `test_transform_handles_empty_dataframe`
- Mock external dependencies (API calls, database)
- Aim for good coverage of edge cases

## Submitting Changes

### Pull Request Process

1. Ensure your code passes all tests and linting
2. Update documentation if needed
3. Add tests for new functionality
4. Create a pull request with a clear description
5. Link any related issues

### PR Description Template

```markdown
## Summary
Brief description of changes.

## Changes
- Change 1
- Change 2

## Testing
How were these changes tested?

## Related Issues
Fixes #123
```

## Reporting Issues

### Bug Reports

Include:
- Python version and OS
- Steps to reproduce
- Expected vs actual behavior
- Error messages or logs
- Screenshots if applicable

### Feature Requests

Include:
- Use case description
- Proposed solution
- Alternative solutions considered

## Questions?

- Open a GitHub issue for questions
- Check existing issues and documentation first

Thank you for contributing!
