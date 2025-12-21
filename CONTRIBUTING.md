# Contributing to Cascade

First off, thank you for considering contributing to Cascade! It's people like you that make Cascade such a great tool.

Following these guidelines helps to communicate that you respect the time of the developers managing and developing this open source project. In return, they should reciprocate that respect in addressing your issue or assessing patches and features.

## Getting Started

### Setting Up the Development Environment

The Cascade repository is a monorepo managed with `uv`. We have consolidated all development and testing dependencies into a single `[dev]` extra in the root `pyproject.toml`.

To set up your environment for development, please follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/doucx/Cascade.git
    cd Cascade
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install in editable mode with all dev dependencies:**
    This is the single most important step. This command installs all sub-packages in editable mode and pulls in all dependencies required for testing and documentation.

    ```bash
    uv pip install -e .[dev]
    ```

That's it! Your environment is now ready for development.

### Running Tests

To run the entire test suite, simply execute `pytest` from the root of the repository:

```bash
pytest
```

### Code Style

We will be using `ruff` for linting and formatting. Before submitting a pull request, please run:

```bash
# (Coming soon)
# ruff check .
# ruff format .
```

### Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification. This helps us automate changelog generation and makes the project history more readable. Please format your commit messages accordingly.