# Contributing to Filum

Thank you for your interest in contributing to Filum! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to uphold our code of conduct:

- Be respectful and inclusive
- Exercise consideration and empathy
- Focus on what is best for the community
- Keep disagreements constructive

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 22+ (via nvm)
- Docker and Docker Compose
- uv (Python package manager)
- pnpm (Node package manager)

### Development Setup
```bash
# Clone the repository
git clone https://github.com/Mathias-PP/filum.git
cd filum

# Run the setup script
./scripts/setup.sh

# Or manually
make setup
```

## Workflow

### 1. Create a Branch
```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/issue-number
```

### 2. Make Changes
- Follow the project's coding conventions (see CLAUDE.md)
- Write code that is simple and readable
- Add tests for new functionality
- Update documentation as needed

### 3. Commit Changes
We use Conventional Commits. Your commit message should be:

```
<type>(<scope>): <description>

[optional body]
[optional footer]
```

Types:
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, semicolons, etc)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements
- `ci`: CI/CD changes
- `data`: Data pipeline changes

Examples:
```
feat(sources): add Wayback Machine archiving
fix(auth): redirect loop on OAuth callback
docs(api): update endpoint documentation
test(crypto): add tests for signature verification
```

### 4. Push and Create PR
```bash
git push origin feat/your-feature-name
```

Then create a Pull Request on GitHub with:
- Clear description of changes
- Link to related issue
- Screenshots for UI changes
- Testing done

## Development Guidelines

### Python (Backend)
- Use `uv` for package management
- Async by default (FastAPI routes, SQLAlchemy sessions)
- Type hints everywhere
- Run linting: `uv run ruff check .`
- Run type checking: `uv run mypy app/`

### TypeScript (Frontend)
- Strict TypeScript mode
- Run linting: `pnpm lint`
- Run formatting: `pnpm format`

### Database
- All schema changes via Alembic migrations
- Never modify production data directly
- Test migrations before merging

### Testing
- Write tests for business logic
- Aim for meaningful coverage, not 100%
- Integration tests for API endpoints

## Pull Request Process

1. Ensure all CI checks pass
2. Update documentation if needed
3. Add entry to CHANGELOG.md
4. Request review from maintainers
5. After approval, squash and merge

## Areas for Contribution

### Backend
- API endpoints
- Authentication (OAuth)
- Cryptographic signing
- Source extraction and archiving

### Frontend
- UI components
- Graph visualization (D3.js)
- User interface

### Data Engineering
- dbt models and transformations
- Data quality checks
- Analytics pipeline

### Infrastructure
- Docker configurations
- CI/CD pipelines
- Monitoring and logging

## Questions?

Feel free to open an issue for questions about contributing.

---

*This contributing guide is inspired by [Conventional Commits](https://www.conventionalcommits.org/) and open source best practices.*
