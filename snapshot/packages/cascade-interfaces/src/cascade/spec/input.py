from typing import Any
from dataclasses import dataclass


@dataclass(frozen=True)
class InputSpec:
    """描述一个外部输入契约的元数据基类。"""

    name: str
    default: Any = None
    description: str = ""
    # 注意: 'required' 属性被移除，其逻辑由 'default' 是否存在来隐式定义。
    # 运行时若无 default 且未提供值，则会失败。


@dataclass(frozen=True)
class ParamSpec(InputSpec):
    """描述一个命令行参数的元数据。"""

    type: Any = str  # 用于 CLI 类型转换


@dataclass(frozen=True)
class EnvSpec(InputSpec):
    """描述一个环境变量的元数据。"""

    pass
