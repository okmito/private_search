# Contributing to PrivateSearch

Thank you for your interest in contributing to PrivateSearch! This document provides guidelines for contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. Please be respectful, inclusive, and constructive in all interactions.

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ with pgvector extension
- Git

### Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/privatesearch.git`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Set up the development environment (see README.md)
5. Make your changes
6. Run tests and linting
7. Submit a pull request

## Development Workflow

### Branching Strategy

- `main` — Stable, production-ready code
- `feature/*` — New features
- `fix/*` — Bug fixes
- `docs/*` — Documentation changes
- `refactor/*` — Code refactoring
- `test/*` — Test additions or improvements

### Commit Messages

Follow conventional commits format:

```
feat(index): implement persistent inverted index
fix(crawler): handle redirect loops in URL frontier
docs(ranking): document BM25 parameters
test(retrieval): add BM25 regression tests
refactor(api): simplify search endpoint validation
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`, `security`

### Pull Request Process

1. Ensure your branch is up to date with `main`
2. Run all tests: `pytest` (backend) and `npm test` (frontend)
3. Run linters: `ruff check .` and `npm run lint`
4. Run formatter: `ruff format .` and `npm run format`
5. Update documentation if needed
6. Add tests for new functionality
7. Submit PR with clear description of changes

## Coding Standards

### Python

- Follow PEP 8 (enforced by Ruff)
- Type hints required for all public functions
- Docstrings for public modules, classes, and functions
- Maximum line length: 100 characters
- Use `async`/`await` for I/O operations

### TypeScript/React

- Follow project ESLint/Prettier configuration
- TypeScript strict mode enabled
- Functional components with hooks
- Proper error boundaries

### Database

- Use Alembic for migrations
- Never commit destructive migrations without review
- Index foreign keys and frequently queried columns

## Testing Requirements

Every meaningful change must include tests:

1. **Unit tests** — Test individual functions/classes in isolation
2. **Integration tests** — Test component interactions
3. **E2E tests** — Test complete user flows

Before submitting:
- All existing tests must pass
- New tests must cover the changed functionality
- Test coverage should not decrease

## Documentation

- Update README.md for user-facing changes
- Update docs/ for architecture/design changes
- Add docstrings for new public APIs
- Keep AGENTS.md current with process changes

## Security

- Never commit secrets, API keys, or credentials
- Report security issues privately (see SECURITY.md)
- Validate all external inputs
- Follow SSRF protection guidelines for crawler changes

## Dependency Management

- Prefer standard library over external dependencies
- Justify new dependencies in PR description
- Keep dependencies updated (security patches)
- Use `pip-audit` and `npm audit` regularly

## Benchmarking

- Run benchmarks for ranking/search changes
- Never fabricate benchmark results
- Document methodology in benchmark results

## Review Process

PRs require:
- At least one approval from a maintainer
- All CI checks passing
- No unresolved review comments

Maintainers will review within 3 business days.

## Release Process

Releases follow semantic versioning (MAJOR.MINOR.PATCH).

Maintainers handle releases:
1. Update version in pyproject.toml and package.json
2. Generate changelog
3. Create GitHub release
4. Publish to PyPI/npm (when applicable)

## Questions?

Open a GitHub Discussion or reach out to maintainers.

Thank you for contributing to PrivateSearch!