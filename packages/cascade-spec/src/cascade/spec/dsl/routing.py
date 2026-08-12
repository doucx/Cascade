from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .fluent import LazyResult  # NEW


@dataclass
class Router:
    selector: LazyResult[Any]
    routes: dict[Any, LazyResult[Any]]
