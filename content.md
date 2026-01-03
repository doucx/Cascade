好的，我们立即着手清理这些不符合公理的命名。这是一次精确的外科手术，旨在消除代码中的语义模糊性，为后续更大规模的重构铺平道路。

我将生成一个计划，通过 `patch_file` 指令精确地修复 linter 报告的 5 个命名违规。

## [WIP] fix: 将哈希变量名与架构公理对齐

### 用户需求

修复 `lint_hash_names.py` 脚本报告的 5 个哈希命名违规，确保 `cascade-graph` 和 `cascade-spec` 包中的相关变量名严格遵循《哈希强制长命名规范 v3.0》。

### 评论

这是一次至关重要的“代码卫生”清理。遵循严格的命名公理能够消除代码中的“语义债务”，使得任何开发者（包括 AI）在阅读代码时都能立即理解变量的真实角色——它是用于链接的“规范 ID”，还是用于比较的“瞬时快照”。这是我们进行更深层次重构、解耦 `engine` 和 `graph` 的安全前提。

### 目标

1.  重命名 `cascade-spec` 中的 `validated_hashes`。
2.  重命名 `cascade-graph` 中 `reflection.py` 的 `structure_hash`。
3.  重命名 `cascade-graph` 中 `hashing.py` 的 `code_hash`。
4.  重命名 `cascade-graph` 中 `build.py` 的两处 `node_hash`。

### 基本原理

我们将使用 `patch_file` 指令，针对 linter 报告的每一处违规，提供足够大的上下文代码块进行精确替换。通过将违规的短命名（如 `node_hash`）替换为符合 `[State]_[Source]_[Object]_hash` 范式的长命名（如 `current_node_instance_hash`），我们可以从根本上消除歧义，使代码库与架构公理保持一致。

### 标签

#intent/fix #flow/ready #priority/high #comp/graph #comp/spec #scope/dx #ai/instruct #task/domain/refactoring #task/object/naming-convention #task/action/enforcement #task/state/begin

---

### Script

#### Acts 1: 修正 `cascade-spec` 中的容器命名

首先，我们修正 `fingerprint.py` 中被 linter 误判为哈希变量的字典容器。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/fingerprint.py
~~~~~
~~~~~python.old
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fingerprint":
        validated_hashes = {}
        for key, value in data.items():
            cls._validate_key(key)
            if value is not None:
                validated_hashes[key] = str(value)
        return cls(_hashes=validated_hashes)
~~~~~
~~~~~python.new
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fingerprint":
        internal_hashes = {}
        for key, value in data.items():
            cls._validate_key(key)
            if value is not None:
                internal_hashes[key] = str(value)
        return cls(_hashes=internal_hashes)
~~~~~

#### Acts 2: 修正 `cascade-graph` 中的哈希变量命名

接下来，我们依次修复 `cascade-graph` 包内的四个违规。

首先是 `reflection.py` 中的 `structure_hash`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/analysis/reflection.py
~~~~~
~~~~~python.old
        # We compute a structural hash based on the definition's content.
        structure_hash = self._compute_structure_hash(
            name, args, return_annotation, docstring, is_async, mode
        )

        fingerprint = Fingerprint()
        fingerprint["current_code_structure_hash"] = structure_hash
~~~~~
~~~~~python.new
        # We compute a structural hash based on the definition's content.
        current_code_structure_hash = self._compute_structure_hash(
            name, args, return_annotation, docstring, is_async, mode
        )

        fingerprint = Fingerprint()
        fingerprint["current_code_structure_hash"] = current_code_structure_hash
~~~~~

然后是 `hashing.py` 中的 `code_hash`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python.old
        # 1. Start with the Stable Code Fingerprint
        code_hash = definition.fingerprint["current_code_structure_hash"]
        components = [f"CodeHash:{code_hash}"]
~~~~~
~~~~~python.new
        # 1. Start with the Stable Code Fingerprint
        current_code_structure_hash = definition.fingerprint["current_code_structure_hash"]
        components = [f"CodeHash:{current_code_structure_hash}"]
~~~~~

最后，我们修复 `build.py` 中的两处 `node_hash` 违规。

第一处，在 `_visit_lazy_result` 方法中：

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
        # 3. Compute Node Instance Hash
        node_hash = self.hashing_service.compute_node_instance_hash(
            task_def, result, dep_nodes
        )

        # 4. Hash-consing / Create Node
        node = self.registry.get(node_hash)
        if not node:
            # Extract bindings (Literals)
            input_bindings = {}
            for i, val in enumerate(result.args):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[str(i)] = val
            for k, val in result.kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            # Complexity check
            from cascade.spec.resource import Inject as InjectMarker
            from cascade.common.inputs import _get_param_value

            has_complex = False
            if result.task.func is _get_param_value.func:
                has_complex = True

            # Note: Signature check is now implicit in TaskDef/Analyzer?
            # We still need to check for Inject markers in defaults, but ReflectionAnalyzer
            # serialized defaults to strings. We might need raw access here or rely on runtime.
            # For now, let's keep the simplistic check if possible, or assume analyzer handled it?
            # Actually, we need to inspect the raw function again for runtime injection logic.
            # This is a runtime concern, so inspecting result.task.func is fine.
            if not has_complex:
                try:
                    sig = inspect.signature(result.task.func)
                    has_complex = any(
                        isinstance(p.default, InjectMarker)
                        for p in sig.parameters.values()
                    )
                except ValueError:
                    pass

            if not has_complex:

                def is_complex_value(v):
                    if isinstance(v, InjectMarker):
                        return True
                    if isinstance(v, list):
                        return any(is_complex_value(x) for x in v)
                    if isinstance(v, dict):
                        return any(is_complex_value(x) for x in v.values())
                    return False

                has_complex = any(is_complex_value(v) for v in input_bindings.values())

            # Note: execution_mode is now part of task_def (definition.mode)
            if result.task.func is _get_param_value.func:
                # Retrieve the ParamSpec from the global context to attach to the node
                from cascade.common.context import get_current_context

                # The arg at index 0 is the param name
                param_name = input_bindings.get("0") or input_bindings.get("name")
                param_spec = None
                if param_name:
                    ctx = get_current_context()
                    # Linear scan is okay for build time, or we could optimize context lookup
                    for spec in ctx.get_all_specs():
                        if spec.name == param_name:
                            # We import inside to avoid top-level circular imports if possible,
                            # though ParamSpec is imported in ParamNode definition
                            from cascade.spec.input import ParamSpec

                            if isinstance(spec, ParamSpec):
                                param_spec = spec
                            break

                node = ParamNode(
                    structural_id=node_hash,
                    definition=task_def,
                    node_type="param",
                    _callable=result.task.func,
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    param_spec=param_spec,
                    has_complex_inputs=True,
                )
            else:
                node = TaskNode(
                    structural_id=node_hash,
                    definition=task_def,
                    _callable=result.task.func,
                    node_type="task",
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    has_complex_inputs=has_complex,
                )
            self.registry._registry[node_hash] = node
~~~~~
~~~~~python.new
        # 3. Compute Node Instance Hash
        current_node_instance_hash = self.hashing_service.compute_node_instance_hash(
            task_def, result, dep_nodes
        )

        # 4. Hash-consing / Create Node
        node = self.registry.get(current_node_instance_hash)
        if not node:
            # Extract bindings (Literals)
            input_bindings = {}
            for i, val in enumerate(result.args):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[str(i)] = val
            for k, val in result.kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            # Complexity check
            from cascade.spec.resource import Inject as InjectMarker
            from cascade.common.inputs import _get_param_value

            has_complex = False
            if result.task.func is _get_param_value.func:
                has_complex = True

            # Note: Signature check is now implicit in TaskDef/Analyzer?
            # We still need to check for Inject markers in defaults, but ReflectionAnalyzer
            # serialized defaults to strings. We might need raw access here or rely on runtime.
            # For now, let's keep the simplistic check if possible, or assume analyzer handled it?
            # Actually, we need to inspect the raw function again for runtime injection logic.
            # This is a runtime concern, so inspecting result.task.func is fine.
            if not has_complex:
                try:
                    sig = inspect.signature(result.task.func)
                    has_complex = any(
                        isinstance(p.default, InjectMarker)
                        for p in sig.parameters.values()
                    )
                except ValueError:
                    pass

            if not has_complex:

                def is_complex_value(v):
                    if isinstance(v, InjectMarker):
                        return True
                    if isinstance(v, list):
                        return any(is_complex_value(x) for x in v)
                    if isinstance(v, dict):
                        return any(is_complex_value(x) for x in v.values())
                    return False

                has_complex = any(is_complex_value(v) for v in input_bindings.values())

            # Note: execution_mode is now part of task_def (definition.mode)
            if result.task.func is _get_param_value.func:
                # Retrieve the ParamSpec from the global context to attach to the node
                from cascade.common.context import get_current_context

                # The arg at index 0 is the param name
                param_name = input_bindings.get("0") or input_bindings.get("name")
                param_spec = None
                if param_name:
                    ctx = get_current_context()
                    # Linear scan is okay for build time, or we could optimize context lookup
                    for spec in ctx.get_all_specs():
                        if spec.name == param_name:
                            # We import inside to avoid top-level circular imports if possible,
                            # though ParamSpec is imported in ParamNode definition
                            from cascade.spec.input import ParamSpec

                            if isinstance(spec, ParamSpec):
                                param_spec = spec
                            break

                node = ParamNode(
                    structural_id=current_node_instance_hash,
                    definition=task_def,
                    node_type="param",
                    _callable=result.task.func,
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    param_spec=param_spec,
                    has_complex_inputs=True,
                )
            else:
                node = TaskNode(
                    structural_id=current_node_instance_hash,
                    definition=task_def,
                    _callable=result.task.func,
                    node_type="task",
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    has_complex_inputs=has_complex,
                )
            self.registry._registry[current_node_instance_hash] = node
~~~~~

第二处，在 `_visit_mapped_result` 方法中：

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
        # Compute Hash
        node_hash = self.hashing_service.compute_node_instance_hash(
            task_def, result, dep_nodes
        )

        node = self.registry.get(node_hash)
        if not node:
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            node = MapNode(
                structural_id=node_hash,
                definition=task_def,
                node_type="map",
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )
            self.registry._registry[node_hash] = node
~~~~~
~~~~~python.new
        # Compute Hash
        current_node_instance_hash = self.hashing_service.compute_node_instance_hash(
            task_def, result, dep_nodes
        )

        node = self.registry.get(current_node_instance_hash)
        if not node:
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            node = MapNode(
                structural_id=current_node_instance_hash,
                definition=task_def,
                node_type="map",
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )
            self.registry._registry[current_node_instance_hash] = node
~~~~~

### 下一步建议

1.  **验证**: 执行此计划后，再次运行 `scripts/lint_hash_names.py` 以确认所有 `hash` 相关的违规都已清除。
2.  **深入**: 运行 `scripts/lint_hash_names.py . --check-ids`，全面盘点 `engine` 和 `graph` 中所有模糊的 `_id` 类命名。这将为我们下一步对 `structural_id` 本身的重构提供一份清晰、可执行的清单。
