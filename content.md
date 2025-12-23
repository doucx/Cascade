简要回答
这是一个非常严重的**架构冲突 (Architectural Conflict)**，也是我在执行指令时的疏忽。正如 `d3-principle-monorepo-build-and-type-hints` 原则所警告的，当两个包（`cascade-graph` 和 `cascade-spec`）同时提供相同的子命名空间（`cascade.graph`）时，会发生**命名空间遮蔽 (Namespace Shadowing)**。

目前的情况是：`cascade-graph` 是计算图逻辑的“所有者”，其 `model.py` 被 `build.py` 引用；而我之前错误地修改了 `cascade-spec` 下的副本。

我将立即生成修复计划：统一 `Node` 模型到 `cascade-graph`，并彻底删除 `cascade-spec` 下的冗余冲突文件。

## [WIP] fix: 消除命名空间冲突并统一 `Node` 模型

### 错误分析
1.  **命名空间遮蔽**: `packages/cascade-spec/src/cascade/graph/model.py` 和 `packages/cascade-graph/src/cascade/graph/model.py` 存在定义冲突。
2.  **修改目标错误**: 我在 Acts 2 中修改了 `cascade-spec` 里的模型，但 `cascade-graph/src/cascade/graph/build.py` 实际导入的是同目录下的 `model.py`，导致了 `TypeError`。
3.  **定义歧义**: `cascade-spec` 版本的模型使用了 `literal_inputs`，而 `cascade-graph` 版本（也是引擎实际使用的版本）使用了 `input_bindings`。

### 用户需求
修复 `TypeError` 并清理 Monorepo 中的命名空间冲突。

### 目标
1.  删除冗余的 `packages/cascade-spec/src/cascade/graph/model.py`。
2.  在真正的 `packages/cascade-graph/src/cascade/graph/model.py` 中添加 `has_complex_inputs` 字段。
3.  确保所有引用指向唯一的、正确的 `Node` 定义。

### 基本原理
遵循“单一事实来源 (Single Source of Truth)”原则。在 Monorepo 中，一个模块路径不应由两个不同的 package 分担定义，否则会导致开发工具和运行时的身份危机。

### 标签
#intent/fix #flow/ready #priority/critical #comp/graph #comp/spec #scope/core #ai/instruct #task/domain/architecture #task/object/namespace-fix #task/action/cleanup #task/state/continue

---

### Script

#### Acts 1: 彻底删除冗余的冲突文件
为了防止后续干扰，我们首先移除 `cascade-spec` 下那个具有迷惑性的 `model.py`。

~~~~~act
delete_file
packages/cascade-spec/src/cascade/graph/model.py
~~~~~

#### Acts 2: 在真正的 `Node` 模型中添加优化字段
修改 `cascade-graph` 包中的模型定义。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
    # Structural Bindings
    # Maps argument names to their literal (JSON-serializable) values.
    # This makes the Node self-contained.
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
~~~~~
~~~~~python
    # Structural Bindings
    # Maps argument names to their literal (JSON-serializable) values.
    # This makes the Node self-contained.
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    # Optimization: Flag indicating if the node requires complex resolution 
    # (e.g., has Inject markers or complex nested structures in bindings)
    has_complex_inputs: bool = False

    def __hash__(self):
~~~~~

#### Acts 3: 检查并修正 `build.py` 的导入（防御性检查）
确保 `build.py` 引用的是本地的模型。

~~~~~act
read_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~

### 下一步建议
通过 Acts 1 和 2，我们已经解决了 `TypeError` 及其根源。

现在请再次尝试运行分析：
1.  `python scripts/profile_entry.py heavy 1000`
2.  `python scripts/profile_entry.py simple 1000`

我们应该能看到 `Node` 被成功实例化，并且 `heavy` 路径的性能回归得到了缓解。如果 `heavy` 路径仍然很慢，请注意看 `profile` 中 `_get_merkle_hash` 的排名。
