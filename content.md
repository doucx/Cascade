好的，我们已经系统地清理了 `cascade-spec` 包内的所有循环依赖风险点。现在我们将这些架构修复作为一个完整的逻辑单元提交。

## [COMMIT] fix(spec): resolve circular dependencies by using relative imports and Any

### 用户需求
提交解决 `cascade-spec` 与 `cascade-execution-graph` 以及包内模块之间循环依赖的修复。

### 评论
这是一次重要的架构清理。通过将 `spec` 层对遗留实现层的依赖泛化为 `Any`，并强制在 `spec` 包内部使用相对导入，我们彻底消除了命名空间解析产生的歧义。这不仅解决了当前的 `stitcher check` 报错，也显著增强了底层规范包的健壮性和纯净度，防止未来再次出现类似的依赖塌陷。

### 目标
1.  将修改过的所有 `cascade-spec` 文件添加到 Git 暂存区。
2.  创建一个详尽的提交记录，说明修复的原理和必要性。

### 基本原理
我们遵循了“底层包不感知实现层”和“包内引用优先使用相对路径”的原则。这些原则确保了即使在复杂的 Monorepo 和命名空间包环境下，静态分析工具也能准确、高效地解析依赖关系，而不会被路径重叠所误导。

### 标签
#intent/fix #flow/ready #priority/critical #comp/spec #scope/core #ai/instruct #task/domain/architecture #task/object/dependency-graph #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交架构修复

我们将所有受影响的文件添加到暂存区并创建提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/runtime/interfaces.py
packages/cascade-spec/src/cascade/spec/dsl/fluent.py
packages/cascade-spec/src/cascade/spec/dsl/task.py
packages/cascade-spec/src/cascade/spec/dsl/routing.py
packages/cascade-spec/src/cascade/spec/dsl/jump.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(spec): resolve circular dependencies and namespace resolution cycles

This commit addresses several critical circular dependency issues identified by 'stitcher check'.

1. Decoupled 'cascade-spec' from 'cascade-execution-graph':
   Modified 'interfaces.py' to use 'Any' instead of importing 'Graph' and 'Node' from the legacy execution-graph package. This restores the correct architectural hierarchy where the specification layer has zero knowledge of its implementations.

2. Fixed Namespace Package Resolution Cycles:
   Converted all absolute imports within the 'cascade.spec.dsl' subpackage to relative imports. Using absolute imports (e.g., 'from cascade.spec.dsl.fluent import ...') within a namespace package can lead static analysis tools to incorrectly re-parse the entire namespace starting from other packages (like 'cascade-cli-observer'), creating false dependency loops.

Files updated to use relative imports:
- fluent.py
- task.py
- routing.py
- jump.py

These changes ensure a clean, acyclic dependency graph and improve the reliability of static analysis in complex development environments.
~~~~~

### 下一步建议
- **回归检查**: 运行所有测试套件以确保导入方式的变更没有影响运行时的热加载或插件机制。
- **文档更新**: 可以在内部开发文档中增加关于“包内导入必须使用相对路径”的指导原则，防止未来再次引入类似问题。
