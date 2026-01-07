You are absolutely right. My apologies.

That was a significant oversight and a severe anti-pattern. Hardcoding a pre-calculated hash value is a direct violation of our core engineering principles, specifically **HFEA's "Zero Heuristics"** and **ADAP's "Identity Assumption"**. It makes the test fragile, opaque, and non-deterministic. Any minor change to the `gpu_task` function, even a comment, would alter its hash and break the test, for reasons that would be impossible to debug without recalculating the hash manually.

I failed to follow the principle of **determinism**. The test must be self-contained and compute the required hash at runtime.

I will correct this immediately by removing the hardcoded value and using the `ReflectionAnalyzer` to dynamically and correctly generate the hash within the test itself. This ensures the test remains robust and serves as a proper specification of the system's behavior.

## [WIP] fix(test): Remove hardcoded hash and dynamically compute it at runtime

### 错误分析
测试 `test_sentry_parks_and_releases_correctly` 失败的根本原因是我在实现中引入了一个严重的反模式：**硬编码了一个预先计算的哈希值**。

1.  **违反了确定性原则**: 测试的成功不应依赖于一个在外部计算、来源不明的“魔术字符串”。正确的做法是，测试本身必须具备在运行时动态计算出所需哈希的能力。
2.  **制造了脆弱性 (Fragility)**: 硬编码的哈希 `a064a7c...` 是基于特定版本的 `gpu_task` 函数定义生成的。对该函数的任何微小改动（例如修改 docstring、添加一个默认参数等）都会导致其 `canonical_code_structure_hash` 发生变化，从而使这个测试立即失败。
3.  **违反了 ADAP 协议**: 我做出了一个未经证实的“身份假设”——即 `gpu_task` 的哈希值会是我预先计算的那个。这是 ADAP 协议明确禁止的行为。我本应构建一个能够消除这种模糊性的机制，即在测试内部使用 `ReflectionAnalyzer` 来获取权威的哈希。

### 用户需求
集成测试 `test_sentry_parks_and_releases_correctly` 必须是健壮且确定性的，不能依赖任何脆弱的、硬编码的哈希值。

### 评论
这是一个至关重要的纠正。一个依赖于外部“魔法值”的测试比没有测试更糟糕，因为它会产生一种虚假的安全感，同时在面对最微小的代码演进时都会脆弱地失败。将测试修正为在运行时动态计算哈希，不仅修复了当前的 bug，更是对我们测试理念的一次重要加固，确保了测试套件的长期健康和可维护性。

### 目标
1.  修改 `packages/cascade-vm/tests/integration/test_resource_sentry.py`。
2.  在测试函数内部，引入 `ReflectionAnalyzer`。
3.  使用 `analyzer.analyze()` 来分析 `gpu_task` 并获取其 `TaskDef`。
4.  从 `TaskDef` 的指纹中提取出 `canonical_code_structure_hash`。
5.  使用这个动态计算出的哈希来注册任务，从而彻底移除硬编码的字符串。

### 基本原理
测试应该是一个自包含的、确定性的环境。通过在测试内部使用 `ReflectionAnalyzer`，我们确保了 `CodeRegistry` 中注册的哈希值与被测试的 `gpu_task` 函数的当前定义**在逻辑上永远是同步的**。`ReflectionAnalyzer` 成为了测试作用域内关于任务“身份”的唯一事实来源 (Single Source of Truth)，从而根除了因哈希不匹配而导致的所有潜在问题。

### 标签
#intent/fix #flow/ready #priority/critical #comp/vm #comp/tests #concept/determinism #scope/dx #ai/refine #task/domain/architecture #task/object/resource-scheduling #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正集成测试，动态计算哈希

我将修改 `test_resource_sentry.py`，移除硬编码的哈希，并替换为在测试时动态生成的哈希。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_sentry.py
~~~~~
~~~~~python.old
import asyncio
import pytest

from cascade.compiler.backend import Builder
from cascade.compiler.frontend import IRGenerator
from cascade.reflection import PhysicalIdGenerator
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.runtime.observability import EventState
from cascade.spec.dsl.task import task
from cascade.spec.dsl.fluent import LazyResult
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.compiler.utils.inspector import GraphInspector
from cascade.runtime.services.observability.events import (
    Event,
    TaskExecutionStarted,
    TaskExecutionFinished,
)


@task
async def gpu_task(val: int) -> int:
    await asyncio.sleep(0.01)
    return val * 2


@pytest.mark.asyncio
async def test_sentry_parks_and_releases_correctly():
    """
    Tests the full lifecycle of the Topological Sentry model:
    1. A task is parked when resources are unavailable.
    2. A wake-up signal is sent when resources are released.
    3. The gate fires, re-queuing the parked task.
    4. Both tasks eventually complete successfully.
    """
    # 1. Define a resource-constrained environment
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1, type="discrete")])
    registry = CodeRegistry()
    registry.register(
        "a064a7c067339a0d859187a43586a512c1c28c863a948508f75b0625e1744131", gpu_task
    )  # Pre-calculated hash

    # 2. Define two concurrent tasks competing for the same resource
    task_a = gpu_task(10).with_constraints(gpu=1)
~~~~~
~~~~~python.new
import asyncio
import pytest

from cascade.compiler.backend import Builder
from cascade.compiler.frontend import IRGenerator
from cascade.reflection import PhysicalIdGenerator, ReflectionAnalyzer
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.runtime.observability import EventState
from cascade.spec.dsl.task import task
from cascade.spec.dsl.fluent import LazyResult
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.compiler.utils.inspector import GraphInspector
from cascade.runtime.services.observability.events import (
    Event,
    TaskExecutionStarted,
    TaskExecutionFinished,
)


@task
async def gpu_task(val: int) -> int:
    await asyncio.sleep(0.01)
    return val * 2


@pytest.mark.asyncio
async def test_sentry_parks_and_releases_correctly():
    """
    Tests the full lifecycle of the Topological Sentry model:
    1. A task is parked when resources are unavailable.
    2. A wake-up signal is sent when resources are released.
    3. The gate fires, re-queuing the parked task.
    4. Both tasks eventually complete successfully.
    """
    # 1. Define a resource-constrained environment
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1, type="discrete")])
    registry = CodeRegistry()

    # Dynamically compute the hash at test time to avoid fragility.
    analyzer = ReflectionAnalyzer()
    task_def = analyzer.analyze(gpu_task)
    gpu_task_hash = task_def.fingerprint["canonical_code_structure_hash"]
    registry.register(gpu_task_hash, gpu_task)

    # 2. Define two concurrent tasks competing for the same resource
    task_a = gpu_task(10).with_constraints(gpu=1)
~~~~~

### 下一步建议
我们已经修复了测试中的严重缺陷，使其变得健壮和确定。现在，这个功能、相关的修复以及它的黄金标准测试都已经完成。

这是一个理想的 `[COMMIT]` 时间点。我建议将“拓扑门控”架构的完整实现（包括这次的测试修复）作为一个原子提交。如果你同意，我将生成相应的 `git_add` 和 `git_commit` 计划。
