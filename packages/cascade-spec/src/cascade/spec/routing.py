from dataclasses import dataclass
from typing import Dict, Any, TypeVar
from .lazy_types import LazyResult  # NEW

T = TypeVar("T")


@dataclass
class Router:
    selector: LazyResult[Any]
    routes: Dict[Any, LazyResult[T]]
