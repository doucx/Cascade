简要回答
我们将把 `stitcher` 项目中的 `Fingerprint` 逻辑及其命名公理移植到 `cascade-spec` 包中。这确立了 `[State]_[Source]_[Object]_[Type]` 的哈希命名规范，为后续的 IR 系统奠定基础。

## [WIP] feat(spec): 引入 Fingerprint 类及命名公理

### 用户需求
将 `stitcher` 项目中用于规范化哈希命名的 `Fingerprint` 类及相关公理（Axiom）移植到 Cascade 中。这包括强制执行 `^(baseline|current)_[a-z]+_[a-z]+_(hash|text)$` 的正则表达式校验。

### 评论
这是一个纯粹的规范引入，不改变现有运行时逻辑。它为解决“概念模糊与哈希脆弱性”问题提供了数据结构基础，强制执行了 `State_Source_Object_Type` 的长命名规范，消除了概念性债务。

### 目标
1.  在 `cascade.spec` 中创建 `fingerprint.py`。
2.  在 `cascade.spec` 导出口暴露 `Fingerprint` 和异常。

### 基本原理
复用 `stitcher` 的成熟设计。`Fingerprint` 类不仅仅是一个字典封装，它是一个“可验证的类型”，确保了在系统各处流转的哈希值都携带了完整的语义上下文（来源、对象、状态），防止了错误类型的哈希被混用。

### 标签
#intent/architect #flow/ready #priority/high #comp/interfaces #concept/state #scope/core #ai/copy-paste #task/domain/core #task/object/fingerprint #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建 Fingerprint 规范文件

我们将直接使用 `stitcher` 的实现，将其放置在 `cascade-spec` 包中。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/fingerprint.py
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

#### Acts 2: 导出 Fingerprint

更新 `packages/cascade-spec/src/cascade/spec/__init__.py` 以导出新的类。此前该文件为空。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python
from .fingerprint import Fingerprint, InvalidFingerprintKeyError

__all__ = ["Fingerprint", "InvalidFingerprintKeyError"]
~~~~~

### 下一步建议
Fingerprint 基础已就绪。下一步应开始实现 IR 层 (`cascade.spec.ir`)，定义 `TaskDef` 和 `ArgumentDef`，并将 Fingerprint 作为其核心属性之一，这是解构 `Node` 对象的关键步骤。
