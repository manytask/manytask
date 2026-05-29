"""Sourcecraft-related utility functions."""

import re


def normalize_string(text: str) -> str:
    """Normalize string by applying multiple transformation rules.

    Rules applied:
    1. Convert all letters to lowercase
    2. Replace [\\s_.@]+ with '-'
    3. Remove all characters not matching [A-Za-z0-9\\-]
    4. Replace multiple consecutive dashes with single dash
    5. Strip leading and trailing dashes

    :param text: Input string to normalize
    :return: Normalized string suitable for use as slug
    """
    # 1. Convert to lowercase
    result = text.lower()

    # 2. Replace spaces, underscores, dots, @ with dashes
    result = re.sub(r"[\s_.@]+", "-", result)

    # 3. Remove all characters not matching [A-Za-z0-9\-]
    result = re.sub(r"[^A-Za-z0-9\-]+", "", result)

    # 4. Replace multiple consecutive dashes with single dash
    result = re.sub(r"-{2,}", "-", result)

    # 5. Strip leading and trailing dashes
    result = result.strip("-")

    return result
