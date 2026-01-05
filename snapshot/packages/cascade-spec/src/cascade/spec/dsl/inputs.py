from typing import Any
from dataclasses import dataclass


@dataclass(frozen=True)
class InputSpec:
    name: str
    default: Any = None
    description: str = ""
    # NOTE: The 'required' attribute is removed; its logic is implicitly defined
    # by whether 'default' is present. A runtime error will occur if no default
    # is set and no value is provided.


@dataclass(frozen=True)
class ParamSpec(InputSpec):
    type: Any = str  # 用于 CLI 类型转换


@dataclass(frozen=True)
class EnvSpec(InputSpec):
    pass
