import html
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
    return name if (re.match(r"^[a-zA-Zа-яА-Я-]{1,50}$", name) is not None) else None


def sanitize_and_validate_comment(comment: str | None, max_length: int = 1000) -> tuple[str | None, str | None]:
    if not comment:
        return None, None
    comment = comment.strip()
    if len(comment) > max_length:
        return None, f"Comment is too long (maximum {max_length} characters)"

    printable_chars_first_idx = 32
    cleaned = "".join(
        char for char in comment if char in "\n\t" or (ord(char) >= printable_chars_first_idx and char.isprintable())
    )

    sanitized = re.sub(r"\n{3,}", "\n\n", html.escape(cleaned)).strip()

    if not sanitized:
        return None, None

    return sanitized, None
