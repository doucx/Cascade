## [COMMIT] fix(examples): 修复 dump_physical_graph.py 的架构兼容性问题

### 用户需求
将对示例脚本 `examples/dump_physical_graph.py` 的修复提交到 Git。

### 评论
此次修复解决了示例脚本与最新 `cascade-spec` 协议不一致的问题，确保新用户在尝试可视化物理图谱时不会遇到阻塞。

### 目标
1. 将修改后的 `examples/dump_physical_graph.py` 添加到暂存区。
2. 创建一个清晰、符合规范的提交记录。

### 基本原理
按照 Quipu 协议，将文件变更后的 Git 操作隔离在独立的 `[COMMIT]` 计划中。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/docs #scope/dx #ai/instruct #task/domain/testing #task/object/examples #task/action/fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交修复

~~~~~act
git_add
examples/dump_physical_graph.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(examples): update dump_physical_graph.py for IR schema changes

Updated the example script to align with recent changes in cascade-spec and cascade-compiler:
- Replaced 'id' with 'current_node_instance_hash' in NodeIR initialization.
- Used Fingerprint.from_dict() class method instead of direct constructor.
- Correctly handled Builder.build() returning a CompilationArtifact instead of a raw graph.
- Switched to using ArgumentKind enum for type safety.
~~~~~

### 下一步建议
示例脚本现已恢复正常。您可以尝试运行它来生成系统的第一个资源竞争图谱：
`python examples/dump_physical_graph.py > graph.dot`
