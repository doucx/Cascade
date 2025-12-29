好的，这是 Cascade V2.0 重构第一阶段的执行计划。

## [WIP] architect: Cascade V2 Phase 0 - Core Foundation

### 用户需求
启动 Cascade V2.0 "Basalt" 架构重构的 Phase 0。
具体任务包括：
1.  建立 `cascade-core` 包的基础结构。
2.  引入核心身份验证系统 `Fingerprint` (基于用户提供的 Axiom 实现)。
3.  定义 IR Level 0 (Definitions) 的基础数据结构。

### 评论
这是向 "Compiler-First" 和 "No Magic Runtime" 架构转变的关键第一步。`Fingerprint` 系统将作为整个 V2 架构中变更检测、缓存和身份验证的公理基础，必须严格实现。新建的 `cascade-core` 包将作为未来所有上层组件（Compiler, Engine）的依赖基石。

### 目标
1.  创建 `packages/cascade-core` 包结构。
2.  实现 `Fingerprint` 类及其校验逻辑。
3.  定义基础 `Definition` 类和初步的 `TaskDef` 结构。

### 基本原理
为了解决 V1 架构中 `Node` 职责过载和运行时类型不安全的问题，我们需要引入显式的中间表示层 (IR)。Phase 0 专注于定义这些 IR 的静态结构（Definitions）以及用于唯一标识它们的机制（Fingerprint），从而为 Phase 2 的编译器实现提供数据基础。

### 标签
#intent/architect #flow/draft #priority/critical
#comp/core #scope/core
#ai/instruct
#task/domain/core #task/object/ir #task/action/define
#task/state/begin #task/status/active

---

### Script

#### Acts 1: 初始化 cascade-core 包结构
我们将创建一个新的包 `cascade-core`，用于存放 V2 的核心数据结构。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-core/src/cascade/core/identity
mkdir -p packages/cascade-core/src/cascade/core/definitions
touch packages/cascade-core/src/cascade/core/__init__.py
touch packages/cascade-core/src/cascade/core/identity/__init__.py
touch packages/cascade-core/src/cascade/core/definitions/__init__.py
~~~~~

#### Acts 2: 配置 pyproject.toml
为新包配置构建元数据。

~~~~~act
write_file
packages/cascade-core/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-core"
version = "2.0.0-alpha"
description = "Core IR and Identity system for Cascade V2"
dependencies = []

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

#### Acts 3: 实现 Fingerprint 系统
根据提供的 Axiom 规范实现指纹系统。

~~~~~act
write_file
packages/cascade-core/src/cascade/core/identity/fingerprint.py
~~~~~
~~~~~python
import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

# Axiom: [State]_[Source]_[Object]_[Type]
# Example: baseline_code_structure_hash, baseline_code_signature_text
# We enforce 4 segments, starting with state, ending with type (hash or text).
FINGERPRINT_KEY_PATTERN = re.compile(r"^(baseline|current)_[a-z]+_[a-z]+_(hash|text)$")


class InvalidFingerprintKeyError(KeyError):
    def __init__(self, key: str):
        super().__init__(
            f"Key '{key}' does not conform to the Fingerprint naming axiom "
            "('^(baseline|current)_[a-z]+_[a-z]+_(hash|text)$')."
        )


@dataclass
class Fingerprint:
    _hashes: Dict[str, str] = field(default_factory=dict)

    @staticmethod
    def _validate_key(key: str) -> None:
        if not FINGERPRINT_KEY_PATTERN.match(key):
            raise InvalidFingerprintKeyError(key)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fingerprint":
        validated_hashes = {}
        for key, value in data.items():
            cls._validate_key(key)
            if value is not None:
                validated_hashes[key] = str(value)
        return cls(_hashes=validated_hashes)

    def to_dict(self) -> Dict[str, str]:
        return self._hashes.copy()

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        # We validate key on read too, to ensure consumer uses correct keys
        self._validate_key(key)
        return self._hashes.get(key, default)

    def __getitem__(self, key: str) -> str:
        self._validate_key(key)
        return self._hashes[key]

    def __setitem__(self, key: str, value: str) -> None:
        self._validate_key(key)
        self._hashes[key] = value

    def __delitem__(self, key: str) -> None:
        self._validate_key(key)
        del self._hashes[key]

    def __contains__(self, key: str) -> bool:
        return key in self._hashes

    def items(self):
        return self._hashes.items()

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Fingerprint):
            return NotImplemented
        return self._hashes == other._hashes
~~~~~

#### Acts 4: 定义 IR Level 0 (Base)
定义所有 DSL 定义的基类。

~~~~~act
write_file
packages/cascade-core/src/cascade/core/definitions/base.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from cascade.core.identity.fingerprint import Fingerprint


@dataclass
class Definition:
    """
    Base class for all IR Level 0 definitions.
    
    A Definition represents a raw declaration from the user DSL (e.g. a Task, a SQL query).
    It is the input to the Compiler, which will lower it into an executable Op.
    """
    
    # The unique identity of this definition, calculated based on its content.
    # Populated by the Compiler during the identification phase.
    fingerprint: Optional[Fingerprint] = None

    # User-defined metadata that does not affect the execution identity
    # (e.g., UI labels, descriptions).
    metadata: Dict[str, Any] = field(default_factory=dict)
~~~~~

#### Acts 5: 定义 IR Level 0 (Task)
定义计算任务的结构。注意这里不再包含 `mapping_factory` 等歧义字段，结构是严格的。

~~~~~act
write_file
packages/cascade-core/src/cascade/core/definitions/model.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Callable, Any, Optional, Dict
from .base import Definition


@dataclass
class TaskDef(Definition):
    """
    Represents a computational task definition.
    Corresponds to functions decorated with @cs.task.
    """
    func: Callable[..., Any]
    name: str
    
    # Configuration policies
    # We use dictionaries for now to avoid circular dependencies with legacy specs,
    # but these will be replaced by strict Policy objects in Phase 1.
    retry_policy: Optional[Dict[str, Any]] = None
    cache_policy: Optional[Dict[str, Any]] = None
    
    def __repr__(self):
        return f"<TaskDef {self.name}>"


@dataclass
class ServiceDef(Definition):
    """
    Represents a configuration for an external service operation.
    Corresponds to helper functions like cs.sql, cs.http.
    
    It does NOT implement map(). It is purely data.
    """
    service_type: str  # e.g. "sql", "http", "ipfs"
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MapDef(Definition):
    """
    Represents a mapping operation over another definition.
    """
    target_def: Definition
    mapping_kwargs: Dict[str, Any]
~~~~~

### 下一步建议
完成基础数据结构定义后，下一步应着手 Phase 1 的工作：
1.  定义更底层的 **Op ADT** (Algebraic Data Types)，如 `ComputeOp`, `ResourceOp`。
2.  开始编写 `Compiler` 的骨架，尝试将 `TaskDef` 转换为 `Op` Graph。
