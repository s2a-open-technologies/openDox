# Contributing to openDox

First off, thank you for considering contributing to openDox! It's people like you that make openDox such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When you create a bug report, please include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples to demonstrate the steps**
- **Describe the behavior you observed and what behavior you expected**
- **Include code samples and screenshots if relevant**
- **Specify your environment:**
  - Python version: `python --version`
  - Node version: `node --version`
  - Docker version: `docker --version`
  - Operating system

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. Please provide:

- **Use a clear and descriptive title**
- **Provide a step-by-step description of the suggested enhancement**
- **Provide specific examples to demonstrate the enhancement**
- **Explain why this enhancement would be useful**

### Pull Requests

1. Fork the repository
2. Create a new branch from `main`: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Run tests and linting
5. Commit your changes with a clear commit message
6. Push to your fork
7. Open a Pull Request

## Development Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker and Docker Compose
- Git

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/opendox.git
cd opendox

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install uv
uv pip install -r pyproject.toml

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start development server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Docker Setup (Recommended)

```bash
# Start all services
docker-compose up --build

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:5000
```

## Security Guidelines

⚠️ **This is a medical application handling patient data. Security is critical.**

### Before Submitting Code

- [ ] **No hardcoded secrets** - Use environment variables
- [ ] **Input validation** - All API inputs must be validated with Pydantic
- [ ] **SQL injection prevention** - Use SQLModel/SQLAlchemy ORM, never raw SQL concatenation
- [ ] **XSS prevention** - React escapes by default, but be careful with `dangerouslySetInnerHTML`
- [ ] **Dependency scanning** - Run `safety check` before submitting

### Secrets Handling

❌ **NEVER DO THIS:**
```python
# Bad - Hardcoded secret
SECRET_KEY = "my-secret-key-123"
```

✅ **DO THIS INSTEAD:**
```python
# Good - Environment variable
import os
SECRET_KEY = os.getenv("SECRET_KEY")
```

### Security Testing

```bash
# Run security scans
pip install safety bandit
safety check
bandit -r backend/

# Run dependency audit
npm audit
```

## Code Style

### Python

We use **Ruff** for linting and formatting:

```bash
# Run linting
ruff check .

# Run formatting
ruff format .
```

**Code style requirements:**
- Follow PEP 8
- Use Google-style docstrings
- Maximum line length: 88 characters
- Use type hints

Example:
```python
def process_user_data(data: Dict[str, str], threshold: float = 0.5) -> List[int]:
    """Process user data and filter by threshold.

    Args:
        data: Dictionary with source data.
        threshold: Filter threshold. Default is 0.5.

    Returns:
        List of processed IDs passing the filter.

    Raises:
        ValueError: If input dictionary is empty.
    """
    if not data:
        raise ValueError("Data dictionary cannot be empty.")
    
    results = [1, 2, 3]
    return results
```

### TypeScript/React

We use **ESLint** for linting:

```bash
cd frontend
npm run lint
```

**Code style requirements:**
- Use TypeScript strict mode
- Prefer functional components with hooks
- Use semantic HTML
- Follow accessibility best practices

## Testing

### Backend Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html

# Run specific test file
pytest tests/test_auth.py
```

### Frontend Tests

```bash
cd frontend

# Run tests
npm run test

# Run with coverage
npm run test:coverage
```

### Integration Tests

```bash
# Run integration tests (requires Docker)
docker-compose -f docker-compose.test.yml up --build
```

## Documentation

- Update the `docs/opendox.md` if you change architecture or add features
- Update `SECURITY.md` if you change security-related code
- Add docstrings to all public functions and classes
- Update API documentation (FastAPI generates OpenAPI automatically)

## Commit Messages

Use conventional commit format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Build process or auxiliary tool changes

**Examples:**
```
feat(auth): add LDAP integration

Adds support for LDAP/Active Directory authentication.
Includes fallback to local auth and auto-provisioning.

Closes #123
```

```
fix(recorder): handle websocket disconnect gracefully

Prevents data loss when network connection drops during recording.
Adds retry logic and session restoration.

Fixes #456
```

## Database Migrations

When changing SQLModels:

```bash
# Generate migration
alembic revision --autogenerate -m "add user preferences"

# Review the generated migration
# Edit if necessary (autogenerate isn't perfect)

# Test migration
alembic upgrade head

# If something goes wrong
alembic downgrade -1
```

**Migration best practices:**
- Always review auto-generated migrations
- Test migrations on a copy of production data
- Include both upgrade and downgrade paths
- Never modify existing migrations that have been applied

## Pull Request Process

1. **Update documentation** for any changed functionality
2. **Add tests** for new features and bug fixes
3. **Ensure all tests pass**:
   ```bash
   pytest
   cd frontend && npm test
   ```
4. **Run security scans**:
   ```bash
   safety check
   bandit -r backend/
   ```
5. **Update the CHANGELOG.md** if applicable
6. **Link related issues** in your PR description
7. **Request review** from maintainers

## Review Criteria

Maintainers will review your PR for:

- **Security**: No vulnerabilities introduced
- **Functionality**: Code works as intended
- **Tests**: Adequate test coverage
- **Documentation**: Updated and clear
- **Style**: Follows project conventions
- **Performance**: No unnecessary performance degradation

## Getting Help

- **General questions**: Open a Discussion on GitHub
- **Bug reports**: Open an Issue
- **Security concerns**: See [SECURITY.md](SECURITY.md)
- **Real-time chat**: Join our Discord/Matrix (if available)

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Credited in security advisories (for security contributions)

## License

By contributing, you agree that your contributions will be licensed under the AGPL-3.0 License.

---

Thank you for contributing to openDox! 🎉
