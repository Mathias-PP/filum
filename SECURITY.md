# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | ✅ Yes             |
| 0.x.x   | ❌ No (EOL)        |

## Reporting a Vulnerability

If you discover a security vulnerability within Filum, please follow these steps:

1. **Do NOT** create a public GitHub issue for the vulnerability.
2. Send a detailed description of the vulnerability via email to security@filum.app
3. Allow up to 48 hours for initial response
4. We will work with you to understand and address the issue promptly
5. Once fixed, we will publicly disclose the vulnerability with credit to the reporter

## Security Best Practices

### Secrets Management
- Never commit secrets to the repository
- Use environment variables for all sensitive configuration
- Rotate secrets regularly
- Use a secrets manager in production (e.g., Railway Variables, AWS Secrets Manager)

### Authentication
- OAuth tokens are handled via HTTP-only cookies
- JWT sessions expire after 24 hours
- Private keys are encrypted at rest using Fernet symmetric encryption

### Data Protection
- PostgreSQL connections use SSL in production
- DuckDB analytics database is isolated from production data
- PII is minimized and encrypted where possible

### API Security
- Rate limiting enabled on all endpoints
- CORS restricted to known origins
- Input validation on all endpoints via Pydantic
- SQL injection prevented via SQLAlchemy ORM

### Dependencies
- Regular dependency updates via Dependabot
- Security scanning with Bandit and Safety
- Container images use minimal base images

## Security Checklist

- [ ] Secrets stored in environment variables, not in code
- [ ] Database credentials rotated regularly
- [ ] API keys for external services (Google OAuth, Wayback) secured
- [ ] HTTPS enforced in production
- [ ] Rate limiting configured appropriately
- [ ] Error messages don't expose internal details
- [ ] Log files don't contain sensitive data
- [ ] Backup data is encrypted
