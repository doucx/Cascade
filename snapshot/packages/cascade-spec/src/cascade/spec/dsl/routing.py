from dataclasses import dataclass
from typing import Dict, Any
from cascade.spec.dsl.fluent import LazyResult  # NEW


@dataclass
class Router:
    selector: LazyResult[Any]
    routes: Dict[Any, LazyResult[Any]]
