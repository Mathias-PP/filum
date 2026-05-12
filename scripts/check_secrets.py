#!/usr/bin/env python3
"""
Script de détection de secrets potentiels dans le code.
Utilisé par pre-commit pour éviter de commiter des credentials.
"""

import re
import sys
from pathlib import Path

SECRET_PATTERNS = [
    (r'password\s*=\s*["\'][^"\']{8,}["\']', 'Potential hardcoded password'),
    (r'secret\s*=\s*["\'][^"\']{8,}["\']', 'Potential hardcoded secret'),
    (r'api[_-]?key\s*=\s*["\'][^"\']{8,}["\']', 'Potential hardcoded API key'),
    (r'client[_-]?secret\s*=\s*["\'][^"\']{8,}["\']', 'Potential hardcoded client secret'),
    (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----', 'Private key detected'),
    (r'AKIA[0-9A-Z]{16}', 'AWS Access Key ID'),
    (r'sk-[live|test]+_[0-9a-zA-Z]{48}', 'OpenAI API Key pattern'),
    (r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,}', 'Slack Token pattern'),
]

EXCLUDE_DIRS = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv',
    'dist', 'build', '.pytest_cache', 'target', 'dbt_packages',
    '.ruff_cache', '.mypy_cache'
}

EXCLUDE_FILES = {
    '.env.example', '.pre-commit-config.yaml', 'check_secrets.py',
    '.secrets.baseline'
}

EXCLUDE_EXTENSIONS = {'.py', '.ts', '.js'}

ALLOWED_PATTERNS = {
    'test_crypto.py',
    'card.py',
    'keygen.py',
}


def should_exclude(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    if path.name in EXCLUDE_FILES:
        return True
    if path.suffix in ['.pyc', '.pyo', '.lock', '.png', '.jpg', '.jpeg', '.gif']:
        return True
    if path.suffix in EXCLUDE_EXTENSIONS and path.name in ALLOWED_PATTERNS:
        return True
    return False


def check_file(path: Path) -> list[tuple[str, str, int]]:
    findings = []
    try:
        content = path.read_text(encoding='utf-8', errors='ignore')
        lines = content.split('\n')
    except Exception:
        return findings

    for i, line in enumerate(lines, 1):
        for pattern, message in SECRET_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append((str(path), message, i))
                break

    return findings


def main():
    root = Path('.')
    all_findings = []

    for path in root.rglob('*'):
        if path.is_file() and not should_exclude(path):
            findings = check_file(path)
            all_findings.extend(findings)

    if all_findings:
        print("⚠️  Potential secrets detected:")
        for file_path, message, line_num in all_findings:
            print(f"  {file_path}:{line_num} - {message}")
        print("\nIf these are false positives, add them to EXCLUDE_FILES or create a .secrets.baseline")
        sys.exit(1)

    print("✅ No obvious secrets detected in staged files")
    sys.exit(0)


if __name__ == '__main__':
    main()
