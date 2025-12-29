from typing import Any
from dataclasses import dataclass


@dataclass(frozen=True)
class InputSpec:
    name: str
    default: Any = None
    description: str = ""
    # 注意: 'required' 属性被移除，其逻辑由 'default' 是否存在来隐式定义。
    # 运行时若无 default 且未提供值，则会失败。


@dataclass(frozen=True)
class ParamSpec(InputSpec):
    type: Any = str  # 用于 CLI 类型转换


@dataclass(frozen=True)
class EnvSpec(InputSpec):
    pass
