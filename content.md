分析正确。当前 `tests` 目录的结构与 `packages` 目录的结构存在明显的不匹配，特别是 `tests/py` 和 `tests/runtime` 目录的存在，破坏了清晰的一一对应关系。这会增加新开发者理解项目的难度，并使查找特定模块的测试变得不直观。

为了解决这个问题，我将提出一个重构计划，目标是使 `tests` 目录的顶层结构严格镜像 `packages` 目录的结构。

## [WIP] refactor(tests): 重组测试套件以镜像包结构

### 用户需求
重构测试套件，使 `tests/` 目录的结构成为 `packages/` 目录结构的直接镜像，以提高可维护性和导航便利性。

### 评论
这是一个非常有价值的开发者体验 (DX) 改进。一个与源代码结构同构的测试套件可以大大降低认知负荷，让开发者能够快速定位、阅读和添加测试。当前 `tests/py` 作为一个“大杂烩”目录，是技术债务的体现，本次重构将彻底偿还它。

### 目标
1.  创建新的、与包名对应的测试目录：`tests/cascade-py` 和 `tests/cascade-runtime`。
2.  将现有 `tests/py`、`tests/cli` 和 `tests/runtime` 目录下的所有测试文件和子目录，迁移到它们在 `packages` 中对应源码的新测试目录中。
3.  删除旧的、结构不正确的目录 (`tests/py`, `tests/cli`, `tests/runtime`)。
4.  确保最终的 `tests` 目录结构清晰、直观，且与 `packages` 保持一致。

### 基本原理
我们将通过一系列文件移动 (`move_file`) 和目录创建/删除 (`run_command`) 操作来完成重构。核心思想是拆解 `tests/py` 这个混合目录，将其中的内容根据其测试对象的真实位置（`cascade-py` 或 `cascade-runtime`）进行重新分配。对于 `tests/cli` 和 `tests/runtime` 中位置不当的单个文件，也将进行迁移。整个过程是纯粹的结构调整，不涉及任何测试代码的逻辑变更。

### 标签
#intent/refine #intent/tooling #flow/ready #priority/medium #comp/tests #scope/dx #ai/brainstorm #task/domain/testing #task/object/directory-structure #task/action/refactor #task/state/begin

---
### Script

#### Acts 1: 创建新的目录结构

首先，我们创建镜像 `packages` 结构的新测试目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p tests/cascade-py/tools
mkdir -p tests/cascade-py/examples
mkdir -p tests/cascade-py/providers
mkdir -p tests/cascade-runtime/adapters/cache
mkdir -p tests/cascade-runtime/adapters/caching
mkdir -p tests/cascade-runtime/adapters/executors
mkdir -p tests/cascade-runtime/adapters/solvers
mkdir -p tests/cascade-runtime/connectors
mkdir -p tests/cascade-runtime/graph
mkdir -p tests/cascade-runtime/runtime
mkdir -p tests/cascade-runtime/integration
mkdir -p tests/cascade-runtime/e2e
~~~~~

#### Acts 2: 迁移 `cascade-runtime` 相关的测试

现在，我们将 `tests/py` 下所有与 `cascade-runtime` 包对应的测试移动到新创建的 `tests/cascade-runtime` 目录中。

~~~~~act
move_file
tests/py/adapters
tests/cascade-runtime/adapters
~~~~~

~~~~~act
move_file
tests/py/connectors
tests/cascade-runtime/connectors
~~~~~

~~~~~act
move_file
tests/py/graph
tests/cascade-runtime/graph
~~~~~

~~~~~act
move_file
tests/py/runtime
tests/cascade-runtime/runtime
~~~~~

~~~~~act
move_file
tests/py/integration
tests/cascade-runtime/integration
~~~~~

~~~~~act
move_file
tests/py/e2e
tests/cascade-runtime/e2e
~~~~~

#### Acts 3: 迁移 `cascade-py` 相关的测试

接着，我们将 `tests/py` 下所有与 `cascade-py` 包对应的测试移动到新创建的 `tests/cascade-py` 目录中。

~~~~~act
move_file
tests/py/tools
tests/cascade-py/tools
~~~~~

~~~~~act
move_file
tests/py/examples
tests/cascade-py/examples
~~~~~

~~~~~act
move_file
tests/py/providers
tests/cascade-py/providers
~~~~~

#### Acts 4: 迁移位置不当的测试文件

现在处理那些放在错误顶层目录中的零散文件。

首先，`tests/cli/test_cli.py` 测试的是 `cascade-py` 中的 `cs.create_cli` 工具，应归属 `cascade-py`。

~~~~~act
move_file
tests/cli/test_cli.py
tests/cascade-py/tools/test_cli.py
~~~~~

其次，`tests/runtime/test_event_bus.py` 应该在 `tests/cascade-runtime/runtime` 中，并重命名以保持一致性。

~~~~~act
move_file
tests/runtime/test_event_bus.py
tests/cascade-runtime/runtime/test_bus.py
~~~~~

#### Acts 5: 清理旧的目录

所有文件都已移动完毕，现在可以安全地删除旧的、空的目录结构。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf tests/py
rm -rf tests/cli
rm -rf tests/runtime
rm -rf tests/connector-local
~~~~~

### 下一步建议
我们已经完成了大规模的目录结构重构。最关键的下一步是**运行完整的测试套件**，以确保在文件移动过程中没有遗漏任何文件，并且所有的测试导入路径和依赖关系依然有效。

你可以执行 `pytest` 来验证重构的正确性。
