"""Email and password validation for auth flows."""

import re

from email_validator import EmailNotValidError, validate_email

PASSWORD_MIN_LENGTH = 8
_PASSWORD_HAS_UPPER = re.compile(r"[A-Z]")
_PASSWORD_HAS_LOWER = re.compile(r"[a-z]")
_PASSWORD_HAS_DIGIT = re.compile(r"\d")
_PASSWORD_HAS_SPECIAL = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?`~]")


def validate_email_address(email: str) -> str:
    """Normalize and validate an email address."""
    try:
        validated = validate_email(email.strip(), check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc
    return validated.normalized.lower()


def validate_password_strength(password: str) -> str:
    """Enforce minimum password complexity for signup."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
        )
    if not _PASSWORD_HAS_UPPER.search(password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not _PASSWORD_HAS_LOWER.search(password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not _PASSWORD_HAS_DIGIT.search(password):
        raise ValueError("Password must contain at least one digit.")
    if not _PASSWORD_HAS_SPECIAL.search(password):
        raise ValueError("Password must contain at least one special character.")
    return password
