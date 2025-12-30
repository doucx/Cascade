好的，我已经仔细阅读了您提供的文件内容。分析证实了您的“白板重构”计划：`ResourceContainer` 的 `setup` 方法在处理 `ResourceDefinition` 时的逻辑不够明确，导致了 `pyright` 的类型推断困难和潜在的调用错误。

我将生成一个计划来精确地执行这个解耦操作。核心改动将发生在 `resource_container.py` 中，使其逻辑更加清晰和健壮。

我将生成一个计划来实现这个改动。

## [WIP] refactor: 解耦 ResourceDefinition 的元数据与提供者函数

### 用户需求
根据“白板重构”计划，将 `ResourceDefinition` 从一个“可调用的包装器”转变为一个“纯粹的数据描述符”，并明确其持有的 `provider_func`。

### 评论
当前 `ResourceDefinition` 的双重身份（既是数据又是函数）违反了单一职责原则，并导致静态分析工具无法正确识别调用契约。通过显式化 `provider_func`，我们可以让 `ResourceContainer` 的初始化逻辑变得透明且类型安全。

### 目标
1.  修改 `cascade-engine` 中 `ResourceContainer` 的 `setup` 方法，使其不再隐式地调用 `ResourceDefinition` 实例。
2.  显式地区分“提供者条目”（可能是 `ResourceDefinition` 或 `Callable`）和“提供者函数”（始终是 `Callable`），以消除类型歧义。
3.  确保修改后的代码能够通过 `pyright` 的静态检查。

### 基本原理
通过将“资源的描述”（Name, Scope）与“资源的构造”（Generator Function）分离，我们建立了一个更稳固的元数据模型。这不仅修复了 `pyright` 报错，也为未来在不运行代码的情况下进行复杂的资源依赖分析奠定了基础。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/spec #comp/engine #concept/resource #scope/core
#ai/instruct
#task/domain/core
#task/object/resource-definition
#task/action/refactor
#task/state/continue

---

### Script

#### Acts 1: 重构 `ResourceContainer` 以显式处理提供者函数

我们将修改 `setup` 方法，引入一个明确的 `provider_func` 变量，并从 `ResourceDefinition` 中提取它，而不是依赖模糊的类型转换。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resource_container.py
~~~~~
~~~~~python.old
            provider_entry = self._resource_providers.get(name)
            if not provider_entry:
                raise NameError(f"Resource '{name}' is required but not registered.")

            # Determine scope and func
            scope = "run"
            func = provider_entry
            if isinstance(provider_entry, ResourceDefinition):
                scope = provider_entry.scope
                func = provider_entry.func

            # Recursive dependency resolution
            sig = inspect.signature(func)
            deps = {
                p_name: get_or_create(p.default.resource_name)
                for p_name, p in sig.parameters.items()
                if isinstance(p.default, Inject)
            }

            # Instantiate
            gen = func(**deps)
            instance = next(gen)
~~~~~
~~~~~python.new
            provider_entry = self._resource_providers.get(name)
            if not provider_entry:
                raise NameError(f"Resource '{name}' is required but not registered.")

            # Determine scope and the actual provider function
            scope = "run"
            provider_func: Callable
            if isinstance(provider_entry, ResourceDefinition):
                scope = provider_entry.scope
                provider_func = provider_entry.func
            else:
                # It's a raw callable, likely for testing or simple cases
                provider_func = provider_entry

            # Recursive dependency resolution
            sig = inspect.signature(provider_func)
            deps = {
                p_name: get_or_create(p.default.resource_name)
                for p_name, p in sig.parameters.items()
                if isinstance(p.default, Inject)
            }

            # Instantiate using the explicitly resolved function
            gen = provider_func(**deps)
            instance = next(gen)
~~~~~

### 下一步建议
我们已经完成了对核心逻辑 `ResourceContainer` 的重构。现在，我建议我们进入 TDD 流程的下一步：更新测试用例以验证我们的修改是正确的，并且没有引入回归。

具体的，我将生成一个计划来：
1.  **检查 `tests/spec/test_resource.py`**：确保现有测试在新的显式逻辑下依然能通过。
2.  **可能增加新测试**：如果现有测试覆盖不足，我会增加一个专门测试 `ResourceContainer.setup` 方法的单元测试，以更精确地验证其行为。

如果你同意，我将生成执行此测试更新的计划。
