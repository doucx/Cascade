I will create and expand the `stitcher.yaml` documentation files for the `cascade-spec` package. This will provide the necessary metadata for the Stitcher tool to resolve symbols and will improve the documentation coverage reported in your `stitcher cov` output.

## [WIP] docs: create and expand Stitcher documentation for cascade-spec

### 用户需求
为 `cascade-spec` 包中的核心 IR、DSL 和编译器接口创建或完善 `stitcher.yaml` 文档。要求使用英文描述，以提高 Stitcher 系统的符号解析率和文档覆盖率。

### 评论
当前 `stitcher cov` 显示 `cascade-spec` 多个模块的覆盖率较低（如 `fluent.py` 仅 8.7%，`graph.py` 仅 25%）。通过完善这些 YAML 文件，我们不仅能提升指标，还能为生成的文档提供更清晰的语义说明。

### 目标
1. 为 `cascade/spec/ir/fingerprint.py` 创建 `fingerprint.stitcher.yaml`。
2. 为 `cascade/spec/compiler/interfaces.py` 创建 `interfaces.stitcher.yaml`。
3. 扩展 `cascade/spec/dsl/fluent.stitcher.yaml` 以覆盖 `RetryPolicy` 以及 `LazyResult` 的各种链式方法。
4. 扩展 `cascade/spec/ir/graph.stitcher.yaml` 以覆盖 `NodeIR` 的所有属性。

### 基本原理
Stitcher 使用 `stitcher.yaml` 作为“影子文档”，将自然语言描述与 Python 源代码中的符号（类、方法、属性）关联起来。提高覆盖率的关键是确保 YAML 中的键值对完整覆盖了 Python 文件中定义的公共 API。

### 标签
#intent/document #flow/ready #priority/medium #comp/spec #comp/docs #scope/dx #ai/instruct #task/domain/documentation #task/object/spec-package #task/action/stitcher-metadata #task/state/begin

---

### Script

#### Acts 1: 为 IR 和 Compiler 接口创建缺少的文档

我们将为指纹识别（Fingerprint）和编译器策略接口提供基本的文档元数据。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/ir/fingerprint.stitcher.yaml
~~~~~
~~~~~yaml
"Fingerprint": |-
  A structured container for Merkle hashes and structural signatures.
  It enforces a specific naming convention (state_source_object_type) to ensure
  architectural consistency across different versions of the system.
"Fingerprint.from_dict": |-
  Hydrates a dictionary into a Fingerprint object, validating all keys.
"Fingerprint.get": |-
  Retrieves a specific hash by its semantic key.
"Fingerprint.to_dict": |-
  Returns a serializable dictionary representation of all hashes.
"InvalidFingerprintKeyError": |-
  Raised when a key does not conform to the required segment-based naming axiom.
~~~~~

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/compiler/interfaces.stitcher.yaml
~~~~~
~~~~~yaml
"ExpansionPolicy": |-
  Protocol defining the Phase 1 (Materialization) contract.
  Policies implementing this are responsible for creating physical nodes
  based on logical IR without establishing cross-subgraph connections.
"WiringPolicy": |-
  Protocol defining the Phase 2 (Wiring) contract.
  Policies implementing this are responsible for establishing connections
  between pre-existing nodes once the physical structure is locked.
"ResourcePrism": |-
  A high-level interface for resource-specific compilation strategies.
  It defines how a logical resource requirement is refracted into
  physical topology (allocators, ledgers, etc.).
~~~~~

#### Acts 2: 扩展 DSL 与 Graph IR 的文档覆盖

我们将细化 `fluent.py` 和 `graph.py` 的文档，涵盖所有的链式调用方法和数据属性。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/dsl/fluent.stitcher.yaml
~~~~~
~~~~~yaml.old
"LazyResult": |-
  A placeholder for the result of a task execution.
  It holds the task that produces it and the arguments passed to that task.
"MappedLazyResult": |-
  Represents the result of mapping a factory over a set of inputs.
  It resolves to a list of results.
~~~~~
~~~~~yaml.new
"RetryPolicy": |-
  Configuration for task-level error recovery and backoff strategies.
"LazyResult": |-
  A placeholder for the result of a task execution.
  It holds the task that produces it and the arguments passed to that task.
"LazyResult.run_if": |-
  Conditional execution: sets a dependency on a boolean-returning LazyResult.
"LazyResult.with_retry": |-
  Attaches a retry policy to the task.
"LazyResult.with_cache": |-
  Attaches a caching policy to the task.
"LazyResult.with_constraints": |-
  Defines resource requirements (e.g., GPU, Memory) for this specific task instance.
"LazyResult.after": |-
  Establishes an explicit sequence dependency (happens-before relationship).
"MappedLazyResult": |-
  Represents the result of mapping a factory over a set of inputs.
  It resolves to a list of results.
"MappedLazyResult.run_if": |-
  Conditional execution for the entire map operation.
"MappedLazyResult.with_retry": |-
  Attaches a retry policy to each individual task in the map.
"MappedLazyResult.after": |-
  Explicit sequencing for the map operation.
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/graph.stitcher.yaml
~~~~~
~~~~~yaml.old
"NodeIR": |-
  Intermediate Representation of a Task instantiation in the logical graph.
  This is the input to the Compiler Backend.
"NodeIR.constraints": |-
  Resource constraints for this node (e.g. {'gpu': 1}).
"NodeIR.inputs": "Mapping of argument names to values. \nValues can be literals or\
  \ references to other NodeIR IDs."
"NodeIR.name": |-
  Human-readable name.
"NodeIR.task": |-
  The definition of the task being invoked.
~~~~~
~~~~~yaml.new
"NodeIR": |-
  Intermediate Representation of a Task instantiation in the logical graph.
  This is the input to the Compiler Backend.
"NodeIR.current_node_instance_hash": |-
  The unique, stable Merkle hash identifying this specific node instance.
"NodeIR.type": |-
  The structural category of the node (task, map, or param).
"NodeIR.logical_id": |-
  The original UUID from the DSL layer, used for cross-layer tracking.
"NodeIR.constraints": |-
  Resource constraints for this node (e.g. {'gpu': 1}).
"NodeIR.inputs": "Mapping of argument names to values. \nValues can be literals or\
  \ references to other NodeIR IDs."
"NodeIR.name": |-
  Human-readable name.
"NodeIR.task": |-
  The definition of the task being invoked.
"NodeIR.condition": |-
  Reference to a node that acts as a gatekeeper for this node's execution.
"NodeIR.dependencies": |-
  List of nodes that must succeed before this node can start.
"NodeIR.flow_control": |-
  Instructions for explicit jumps or iterative loops.
"NodeIR.retry_policy": |-
  Runtime configuration for retrying failed attempts.
"NodeIR.cache_policy": |-
  Configuration for result persistence and retrieval.
~~~~~

### 下一步建议
- **重新运行覆盖率检查**: 执行 `stitcher cov` 以验证 `cascade-spec` 的覆盖率是否显著提升。
- **审查 runtime 包**: `cascade-runtime` 的覆盖率目前也很低（约 10%~30%），建议随后为其核心服务（如 `ConstraintManager` 和 `ResourceManager`）建立类似的文档元数据。
- **生成 HTML 文档**: 尝试使用 `mkdocs` 构建完整的 API 站点，检查 `stitcher` 提供的描述是否能够正确渲染并为开发者提供价值。
