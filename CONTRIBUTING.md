# Contributing to nclutils

Thank you for your interest in contributing to nclutils! This document provides guidelines and instructions to make the contribution process smooth and effective.

## Types of Contributions Welcome

-   Bug fixes
-   Feature enhancements
-   Documentation improvements
-   Test additions

## Development Setup

### Prerequisites

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. To start developing:

1. Install uv using the [recommended method](https://docs.astral.sh/uv/installation/) for your operating system
2. Clone this repository: `git clone https://github.com/natelandau/nclutils`
3. Navigate to the repository: `cd nclutils`
4. Install dependencies with uv: `uv sync`
5. Activate your virtual environment: `source .venv/bin/activate`
6. Install pre-commit hooks: `pre-commit install --install-hooks`

### Running Tasks

[Duty](https://pawamoy.github.io/duty/) is used as our task runner. Common commands:

-   `duty --list` - List all available tasks
-   `duty lint` - Run all linters
-   `duty test` - Run all tests

## Development Guidelines

When developing for nclutils, please follow these guidelines:

-   Write full docstrings
-   All code should use type hints
-   Write unit tests for all new functions
-   Write integration tests for all new features
-   Follow the existing code style

## Commit Process

1. Create a branch for your feature or fix
2. Make your changes
3. Ensure code passes linting with `duty lint`
4. Ensure tests pass with `duty test`
5. Commit using [Commitizen](https://github.com/commitizen-tools/commitizen): `cz c`
6. Push your branch and create a pull request

Use [Semantic Versioning](https://semver.org/) for version management.
