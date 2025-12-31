好的，接下来我们将重构 `cascade-provider-ipfs` 包的测试。

## [WIP] refactor(tests): 分离 cascade-provider-ipfs 的测试

### 用户需求

对 `cascade-provider-ipfs` 包进行测试结构重构。将现有的测试文件迁移到新创建的 `unit/` 或 `integration/` 目录中。

### 评论

`cascade-provider-ipfs` 的测试文件 `test_ipfs.py` 严格来说属于集成测试。它不仅依赖于 `cascade.Engine`、`Solver` 和 `Executor` 的完整堆栈，还依赖于一个复杂的外部模拟（`aiohttp_client` 模拟的 IPFS HTTP API）。这种端到端的验证是集成测试的典型特征。

### 目标

1.  在 `packages/cascade-provider-ipfs/tests/` 目录下创建 `integration/` 目录。
2.  将 `test_ipfs.py` 及其关联的 `.stitcher.yaml` 文件移动到 `integration/` 目录中。

### 基本原理

由于该测试的复杂性完全是为了验证 `ipfs.cat` 和 `ipfs.add` 这两个 Provider 任务在整个 Cascade 运行时环境（包括 HTTP 调用、AIOHTTP 客户端/服务器模拟）中的行为，将其归类为集成测试是最合适的。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-structure #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建 Integration 目录

为 `cascade-provider-ipfs` 创建 `integration` 测试目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-provider-ipfs/tests/integration
~~~~~

#### Acts 2: 迁移集成测试文件

将 `test_ipfs.py` 及其 stitcher YAML 文件移动到 `integration` 目录中。

~~~~~act
move_file
packages/cascade-provider-ipfs/tests/test_ipfs.py
packages/cascade-provider-ipfs/tests/integration/test_ipfs.py
~~~~~
~~~~~act
move_file
packages/cascade-provider-ipfs/tests/test_ipfs.stitcher.yaml
packages/cascade-provider-ipfs/tests/integration/test_ipfs.stitcher.yaml
~~~~~

### 下一步建议

我们已经完成了 `cascade-provider-ipfs` 的重构。现在我们可以继续处理其余的包，如 `pyneedle-pointer`、`pyneedle-runtime` 等。请确认您希望我继续哪个包的重构。
