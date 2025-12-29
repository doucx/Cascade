from dataclasses import dataclass
from typing import Dict, Any
from .lazy_types import LazyResult  # NEW


@dataclass
class Router:
    selector: LazyResult[Any]
    routes: Dict[Any, LazyResult[Any]]
