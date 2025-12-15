from dataclasses import dataclass
from typing import Dict, Any, TypeVar
from .task import LazyResult

T = TypeVar("T")

@dataclass
class Router:
    """
    A dynamic input selector.
    
    It allows a task's argument to be selected at runtime from multiple
    upstream sources based on a selector value.
    """
    selector: LazyResult[Any]
    routes: Dict[Any, LazyResult[T]]