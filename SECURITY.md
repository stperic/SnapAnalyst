# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within SnapAnalyst, please send an email to stperic@outlook.com. All security vulnerabilities will be promptly addressed.

**Please do not report security vulnerabilities through public GitHub issues.**

When reporting a vulnerability, please include:

- Type of vulnerability (e.g., SQL injection, XSS, authentication bypass)
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability

## Security Considerations

### Authentication & Authorization

The current version (0.1.x) is designed for **internal/trusted environments only**. Multi-user authentication and authorization are not fully implemented. For production deployments:

- Implement proper authentication (OAuth2, JWT, etc.)
- Add role-based access control (RBAC)
- Use HTTPS/TLS for all connections
- Secure API endpoints with proper authentication

### Database Security

- All database queries are **read-only** by default
- SQL injection protection through parameterized queries (SQLAlchemy)
- Database credentials should be stored in `.env` files (never committed to git)

### API Keys

- Never commit API keys to the repository
- Use environment variables for all secrets
- Rotate API keys regularly
- Use separate API keys for development/staging/production

### Data Privacy

This application processes SNAP Quality Control data. Ensure compliance with:

- Data handling policies for government datasets
- Privacy regulations (if handling PII)
- Access logging and audit trails for sensitive queries

## Best Practices

1. Keep dependencies up to date (`pip list --outdated`)
2. Run security scans regularly (CodeQL is enabled via GitHub Actions)
3. Review logs for suspicious activity
4. Use strong passwords for database and admin accounts
5. Limit network access to PostgreSQL (firewall rules)
6. Enable CORS restrictions in production
7. Use Docker secrets for sensitive environment variables

## Acknowledgements

We appreciate responsible disclosure of security vulnerabilities.
