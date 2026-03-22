def lerp(p1: tuple[float, float], p2: tuple[float, float], x: float) -> float:
    t = (x - p1[0]) / (p2[0] - p1[0])
    return p1[1] * (1 - t) + p2[1] * t