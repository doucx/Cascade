好的，我们开始执行测试套件的结构重构。

这是一个非常重要的步骤，它能偿还技术债务，使我们的测试架构与源代码的“洋葱架构”保持一致，为后续的开发和维护奠定坚实的基础。

我将生成一个计划来创建新的目录结构，并将所有现有的测试文件移动到它们对应的、符合语义的新位置。

## [WIP] refactor: 重构测试套件以镜像 src 目录结构

### 用户需求
根据之前的分析，重构 `tests/` 目录，使其结构与 `src/cascade/` 的分层架构（`spec`, `graph`, `runtime`, `adapters` 等）保持一致，以提高测试套件的清晰度、可维护性和组织性。

### 评论
这是一次关键的开发者体验 (DX) 优化。扁平化的测试结构已经无法跟上项目复杂度的增长。通过这次重构，我们将建立一个可扩展的、符合架构直觉的测试模式，让任何开发者都能快速地在代码和其对应的测试之间进行导航。

### 目标
1.  在 `tests/` 目录下创建一套新的、与 `src/cascade/` 镜像的子目录结构。
2.  将所有现存的测试文件移动并（在适当时）重命名到其新的、语义正确的路径下。

### 基本原理
我们遵循“约定优于配置”的原则，让测试的物理布局直接反映代码的逻辑架构。这将极大地降低认知负荷。对于那些内容混杂的旧测试文件（如 `test_core_mvp.py` 和 `test_adapters.py`），由于当前工具集的限制（无法原子化地拆分文件），我们将它们暂时移动到最合理的聚合位置（如 `integration` 或 `adapters`），并标记它们为下一步优化的候选对象。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/suite-structure #task/action/refactor #task/state/begin #task/status/active

---

### Script

#### Acts 1: 创建新的目录结构

首先，我们使用一个 `mkdir -p` 命令，一次性地创建所有需要的新目录，确保操作的原子性。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p tests/spec tests/graph tests/runtime tests/adapters/solvers tests/adapters/executors tests/adapters/caching tests/providers tests/tools tests/integration
~~~~~

#### Acts 2: 迁移并重命名测试文件

接下来，我们将每个测试文件精确地移动到其新的位置。

~~~~~act
move_file
tests/test_adapters.py
tests/adapters/test_core_adapters.py
~~~~~
~~~~~act
move_file
tests/test_caching.py
tests/adapters/caching/test_file_existence.py
~~~~~
~~~~~act
move_file
tests/test_control_flow.py
tests/runtime/test_control_flow.py
~~~~~
~~~~~act
move_file
tests/test_core_mvp.py
tests/integration/test_core_mvp.py
~~~~~
~~~~~act
move_file
tests/test_di_and_resources.py
tests/spec/test_resource.py
~~~~~
~~~~~act
move_file
tests/test_end_to_end.py
tests/integration/test_end_to_end.py
~~~~~
~~~~~act
move_file
tests/test_http.py
tests/providers/test_http.py
~~~~~
~~~~~act
move_file
tests/test_map.py
tests/runtime/test_map.py
~~~~~
~~~~~act
move_file
tests/test_retry.py
tests/runtime/test_retry.py
~~~~~
~~~~~act
move_file
tests/test_routing.py
tests/spec/test_routing.py
~~~~~
~~~~~act
move_file
tests/test_runtime_observability.py
tests/runtime/test_bus.py
~~~~~
~~~~~act
move_file
tests/test_spec_async.py
tests/spec/test_async.py
~~~~~
~~~~~act
move_file
tests/test_spec_file.py
tests/spec/test_file.py
~~~~~
~~~~~act
move_file
tests/test_sql.py
tests/providers/test_sql.py
~~~~~
~~~~~act
move_file
tests/test_stdlib.py
tests/providers/test_shell.py
~~~~~
~~~~~act
move_file
tests/test_template.py
tests/providers/test_template.py
~~~~~
~~~~~act
move_file
tests/test_tools.py
tests/tools/test_preview.py
~~~~~

### 下一步建议
我们已经成功地重构了测试套件的目录结构。这是一个巨大的进步。

然而，我们知道 `tests/adapters/test_core_adapters.py` 和 `tests/integration/test_core_mvp.py` 这两个文件的内容是混杂的。下一步，我建议生成一个计划，将这两个文件的内容拆分到更细粒度的、职责单一的测试文件中，例如：

*   从 `test_core_adapters.py` 中拆分出 `tests/adapters/solvers/test_native.py` 和 `tests/adapters/executors/test_local.py`。
*   从 `test_core_mvp.py` 中拆分出 `tests/spec/test_core.py` 和 `tests/graph/test_build.py`。

这将最终完成我们测试套件的架构对齐工作。
