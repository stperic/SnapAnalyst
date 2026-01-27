# GitHub Actions Workflows

Simple CI/CD workflows for SnapAnalyst.

## Workflows

### 🧪 CI (`ci.yml`)
Runs on every push and PR to main:
- Lints code with ruff
- Runs unit tests with PostgreSQL
- Checks test coverage (minimum 25%)

### 🔒 CodeQL (`codeql.yml`)
Security scanning:
- Runs on push/PR to main
- Weekly automated scans
- Detects security vulnerabilities

## Adding Badges to README

Add these badges to your README.md:

```markdown
[![CI](https://github.com/stperic/SnapAnalyst/actions/workflows/ci.yml/badge.svg)](https://github.com/stperic/SnapAnalyst/actions/workflows/ci.yml)
[![CodeQL](https://github.com/stperic/SnapAnalyst/actions/workflows/codeql.yml/badge.svg)](https://github.com/stperic/SnapAnalyst/actions/workflows/codeql.yml)
```

## Optional: Codecov Integration

To enable coverage reporting:

1. Sign up at https://codecov.io
2. Add your repository
3. Get the token and add to GitHub Secrets as `CODECOV_TOKEN`
4. Uncomment these lines in `ci.yml`:

```yaml
    # - name: Upload coverage
    #   uses: codecov/codecov-action@v4
    #   with:
    #     token: ${{ secrets.CODECOV_TOKEN }}
```

Then add badge:
```markdown
[![Coverage](https://codecov.io/gh/stperic/SnapAnalyst/branch/main/graph/badge.svg)](https://codecov.io/gh/stperic/SnapAnalyst)
```
