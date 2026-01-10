好的，我已分析 `CodeRegistry` 的现有实现。

它目前是一个简单的字典包装器，这对于动态注册的基本功能是足够的。由于 Python 的 GIL 保护，单次写入操作是原子性的，因此在单线程异步环境中，我们暂时不需要担心线程安全问题。

然而，为了增强其健壮性并正式化其动态链接的契约，我将执行以下操作：
1.  **增强 `register` 方法**：为其添加一个日志警告，以便在发生哈希冲突（即用一个新函数覆盖一个已存在的哈希）时提供明确的开发者反馈。这符合高保真工程（HFEA）的原则，使系统行为更可观测。
2.  **创建单元测试**: 创建一个新的测试文件，专门验证 `CodeRegistry` 的动态注册行为，包括首次注册、幂等重注册以及哈希冲突场景。这遵循了 TDD 流程，将隐性需求显式化为可验证的契约。

## [WIP] feat(vm): Harden CodeRegistry and add tests for dynamic linking

### 用户需求
根据 VM 实施路线图 1.3，需要增强 `CodeRegistry` 以确保其支持动态链接。这意味着代码注册表必须能够在 `Engine` 启动后，在运行时安全地接受新的 `(hash, callable)` 映射。

### 评论
当前的 `CodeRegistry` 实现是一个简单的字典，虽然功能上可行，但缺少对关键边界情况（如哈希冲突）的明确处理和验证。通过添加日志记录和专门的单元测试，我们不仅能使系统在面对异常情况时更具可观测性，还能将“支持动态注册”这一核心需求固化为一个可长期维护的测试契约，防止未来出现回归。

### 目标
1.  修改 `CodeRegistry.register` 方法，当且仅当一个新的函数试图覆盖一个已存在的、由不同函数对象占用的哈希时，记录一个警告。
2.  在 `packages/cascade-vm/tests/unit/` 目录下创建一个新的测试文件 `test_registry.py`。
3.  在该测试文件中，实现至少三个测试用例：
    *   验证一个函数可以被成功注册和检索。
    *   验证对同一个函数进行重复注册是幂等的，且不会产生警告。
    *   验证当一个不同的函数试图使用相同的哈希注册时，会成功覆盖并记录一条警告。

### 基本原理
`VMExecutionStrategy` 在其生命周期的“链接”阶段需要动态地将从 `CompilationArtifact` 中发现的函数注册到 `CodeRegistry` 中。这个过程必须是可靠和可观测的。通过在 `CodeRegistry` 本身添加防御性代码（日志警告）和外部验证（单元测试），我们确保了这一关键基础设施组件的健壮性，遵循了“先上锁，再加速”的战术原则。

### 标签
#intent/refine #intent/tooling #flow/ready #priority/high #comp/vm #scope/core #scope/dx #task/domain/vm #task/object/code-registry #task/action/harden #task/state/continue

---

### Script

#### Acts 1: 增强 CodeRegistry 以记录哈希冲突

我们首先修改 `registry.py`，为 `register` 方法添加冲突检测逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/registry.py
~~~~~
~~~~~python.old
from typing import Dict, Callable, Any

# A generic callable type for task functions
TaskCallable = Callable[..., Any]


class CodeRegistry:
    def __init__(self):
        self._registry: Dict[str, TaskCallable] = {}

    def register(self, canonical_hash: str, func: TaskCallable) -> None:
        self._registry[canonical_hash] = func

    def get(self, canonical_hash: str) -> TaskCallable:
        if canonical_hash not in self._registry:
            raise KeyError(f"Code for hash '{canonical_hash}' not found in registry.")
        return self._registry[canonical_hash]

    def has(self, canonical_hash: str) -> bool:
        return canonical_hash in self._registry
~~~~~
~~~~~python.new
import logging
from typing import Dict, Callable, Any

# A generic callable type for task functions
TaskCallable = Callable[..., Any]

logger = logging.getLogger(__name__)


class CodeRegistry:
    def __init__(self):
        self._registry: Dict[str, TaskCallable] = {}

    def register(self, canonical_hash: str, func: TaskCallable) -> None:
        if (
            canonical_hash in self._registry
            and self._registry[canonical_hash] is not func
        ):
            logger.warning(
                f"Hash collision detected for '{canonical_hash}'. "
                f"Overwriting registration for '{self._registry[canonical_hash].__name__}' "
                f"with new function '{func.__name__}'."
            )
        self._registry[canonical_hash] = func

    def get(self, canonical_hash: str) -> TaskCallable:
        if canonical_hash not in self._registry:
            raise KeyError(f"Code for hash '{canonical_hash}' not found in registry.")
        return self._registry[canonical_hash]

    def has(self, canonical_hash: str) -> bool:
        return canonical_hash in self._registry
~~~~~

#### Acts 2: 创建单元测试以验证动态注册行为

现在，我们创建一个新的测试文件来锁定 `CodeRegistry` 的行为。

~~~~~act
write_file
packages/cascade-vm/tests/unit/test_registry.py
~~~~~
~~~~~python
import pytest
import logging
from cascade.vm.registry import CodeRegistry


def sample_task_one():
    return "one"


def sample_task_two():
    return "two"


class TestCodeRegistry:
    def test_register_and_get(self):
        """Tests basic registration and retrieval of a function."""
        registry = CodeRegistry()
        sample_hash = "hash_one"

        assert not registry.has(sample_hash)
        registry.register(sample_hash, sample_task_one)

        assert registry.has(sample_hash)
        retrieved_func = registry.get(sample_hash)
        assert retrieved_func is sample_task_one
        assert retrieved_func() == "one"

    def test_get_missing_raises_key_error(self):
        """Tests that getting a non-existent hash raises KeyError."""
        registry = CodeRegistry()
        with pytest.raises(KeyError, match="not found in registry"):
            registry.get("non_existent_hash")

    def test_reregister_idempotent(self, caplog):
        """Tests that re-registering the exact same function is a no-op and does not warn."""
        registry = CodeRegistry()
        sample_hash = "hash_one"

        registry.register(sample_hash, sample_task_one)
        
        with caplog.at_level(logging.WARNING):
            registry.register(sample_hash, sample_task_one)
        
        # No warning should be logged for idempotent re-registration
        assert "Hash collision detected" not in caplog.text
        
        # Ensure the registration is still valid
        assert registry.get(sample_hash) is sample_task_one

    def test_reregister_collision_warns(self, caplog):
        """Tests that registering a different function with the same hash logs a warning."""
        registry = CodeRegistry()
        sample_hash = "hash_collision"

        # Initial registration
        registry.register(sample_hash, sample_task_one)

        # Re-register with a different function
        with caplog.at_level(logging.WARNING):
            registry.register(sample_hash, sample_task_two)

        # A warning should be logged
        assert "Hash collision detected" in caplog.text
        assert f"Overwriting registration for '{sample_task_one.__name__}'" in caplog.text
        assert f"with new function '{sample_task_two.__name__}'" in caplog.text

        # Ensure the registry now holds the new function
        retrieved_func = registry.get(sample_hash)
        assert retrieved_func is sample_task_two
        assert retrieved_func() == "two"
~~~~~

### 下一步建议
我们已经完成了对 `CodeRegistry` 的加固和验证。现在，所有基础设施适配工作都已完成。

是时候进入 **Phase 2: 管理程序构建** 了。我将开始实施核心的 `VMExecutionStrategy` 和 `RuntimeHarness`。
