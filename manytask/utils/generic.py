import re
import secrets


def sanitize_log_data(data: str | None) -> str | None:
    """Sanitize form data."""
    if data is None:
        return None
    sanitized_data = data.replace("\r", "").replace("\n", "")
    return sanitized_data


def generate_token_hex(bytes_count: int = 24) -> str:
    return secrets.token_hex(nbytes=bytes_count)


def lerp(p1: tuple[float, float], p2: tuple[float, float], x: float) -> float:
    t = (x - p1[0]) / (p2[0] - p1[0])
    return p1[1] * (1 - t) + p2[1] * t


def validate_name(name: str) -> str | None:
    return name if (re.match(r"^[a-zA-Zа-яА-Я_-]{1,50}$", name) is not None) else None
