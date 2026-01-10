好的，我们开始执行 Phase 4：依赖清理。

根据你的文件检查结果，`cascade-runtime` 仍然通过 `[project.optional-dependencies]` 保留了对 `python-constraint` 的引用。现在 `Engine` 已经解耦，这个依赖项可以被安全地移除。

## [WIP] chore(runtime): 移除 python-constraint 可选依赖

### 用户需求
执行重构路线图的 Phase 4，从 `cascade-runtime` 包中清理掉所有与 `CSPSolver` 相关的依赖。

### 评论
这是完成 `cascade-runtime` 瘦身的关键一步。通过移除 `pyproject.toml` 中的 `python-constraint` 依赖，我们从包管理的层面上正式确认了 `runtime` 与遗留图求解器的解耦。这确保了用户在安装核心运行时的时候，不会附带安装一个他们可能永远不会使用的库。

### 目标
1.  修改 `packages/cascade-runtime/pyproject.toml` 文件。
2.  从 `[project.optional-dependencies]` 表中移除 `csp_solver` 条目。

### 基本原理
`CSPSolver` 是 `cascade-runtime` 中唯一使用 `python-constraint` 库的组件。在 Phase 2 和 Phase 3 中，`CSPSolver` 及其所属的 `GraphExecutionStrategy` 已经被迁移到了 `cascade-execution-graph` 包中。因此，`cascade-runtime` 不再有任何理由保留对 `python-constraint` 的依赖，无论是直接的还是可选的。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/runtime #comp/build #scope/dx #ai/instruct #task/domain/runtime #task/object/engine #task/action/decouple #task/state/continue

---

### Script

#### Acts 1: 从 `pyproject.toml` 中移除依赖

我们将修改 `cascade-runtime` 的包配置文件，删除对 `python-constraint` 的可选依赖。

~~~~~act
patch_file
packages/cascade-runtime/pyproject.toml
~~~~~
~~~~~toml.old
[project.optional-dependencies]
csp_solver = ["python-constraint"]
redis = ["redis"]
~~~~~
~~~~~toml.new
[project.optional-dependencies]
redis = ["redis"]
~~~~~

### 下一步建议
我们已经成功地完成了 `Engine` 的解耦和 `cascade-runtime` 的依赖清理。根据重构路线图，接下来的任务是 **Phase 5: VM 策略引入 (VM Strategy Introduction)**。

我建议我们开始为新的 `VMExecutionStrategy` 创建骨架文件。这将在 `cascade-runtime` 中建立未来架构的锚点，并为实现基于 VM 的执行器做好准备。如果你同意，我将生成一个计划来创建 `cascade/runtime/strategies/vm.py` 文件和 `VMExecutionStrategy` 类的骨架。
