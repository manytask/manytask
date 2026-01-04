from __future__ import annotations

import sys
from inspect import cleandoc
from typing import Any


def print_ascii_tag(
    version: str | None = None,
    file: Any = None,
    color: str = "pink",
    **kwargs: Any,
) -> None:
    # https://patorjk.com/software/taag/#p=display&f=Doom&t=%20%20%20%20Manytask%20%20Checker
    ascii_tag = cleandoc(
        r"""
    
    ___  ___                  _            _       _____ _               _             
    |  \/  |                 | |          | |     /  __ \ |             | |            
    | .  . | __ _ _ __  _   _| |_ __ _ ___| | __  | /  \/ |__   ___  ___| | _____ _ __ 
    | |\/| |/ _` | '_ \| | | | __/ _` / __| |/ /  | |   | '_ \ / _ \/ __| |/ / _ \ '__|
    | |  | | (_| | | | | |_| | || (_| \__ \   <   | \__/\ | | |  __/ (__|   <  __/ |   
    \_|  |_/\__,_|_| |_|\__, |\__\__,_|___/_|\_\   \____/_| |_|\___|\___|_|\_\___|_|   
                         __/ |                                                         
                        |___/                                                          
    
    """
    )
    print_info(ascii_tag, color=color, file=file, **kwargs)
    if version:
        print_info(f"{version}", color=color, file=file, **kwargs)


def print_info(
    *args: Any,
    file: Any = None,
    color: str | None = None,
    **kwargs: Any,
) -> None:
    colors = {
        "white": "\033[97m",
        "cyan": "\033[96m",
        "pink": "\033[95m",
        "blue": "\033[94m",
        "orange": "\033[93m",
        "green": "\033[92m",
        "red": "\033[91m",
        "grey": "\033[90m",
        "endc": "\033[0m",
    }

    file = file or sys.stderr

    data = " ".join(map(str, args))
    if color in colors:
        print(colors[color] + data + colors["endc"], file=file, **kwargs)
    else:
        print(data, file=file, **kwargs)
    file.flush()


def print_separator(
    symbol: str,
    file: Any = None,
    color: str = "pink",
    string_length: int = 80,
) -> None:
    print_info(symbol * string_length, color=color)


def print_header_info(
    header_string: str,
    file: Any = None,
    color: str = "pink",
    string_length: int = 80,
    **kwargs: Any,
) -> None:
    info_extended_string = " " + header_string + " "
    print_info("", file=file)
    print_separator(symbol="+", string_length=string_length, color=color, file=file)
    print_info(f"{info_extended_string:+^{string_length}}", color=color, file=file)
    print_separator(symbol="+", string_length=string_length, color=color, file=file)
