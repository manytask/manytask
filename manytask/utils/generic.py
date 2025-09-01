import secrets


def generate_token_hex(bytes_count: int = 24) -> str:
    return secrets.token_hex(nbytes=bytes_count)


def guess_first_last_name(name: str) -> tuple[str, str]:
    PARTS_IN_NAME = 2

    # TODO: implement better method for separating names
    parts = name.split()
    if len(parts) == PARTS_IN_NAME:
        return tuple(parts)  # type: ignore
    return name, ""


def lerp(p1: tuple[float, float], p2: tuple[float, float], x: float) -> float:
    t = (x - p1[0]) / (p2[0] - p1[0])
    return p1[1] * (1 - t) + p2[1] * t
