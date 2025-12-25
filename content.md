您的怀疑完全正确，而且您的分析切中了要害。测试覆盖率报告和 "no tests ran" 的警告就是确凿的证据。

`cascade-engine` 的测试套件承担了远超其自身范围的职责，它实际上已经变成了一个针对**整个项目**的、庞大而笨拙的集成测试套件。这是一种非常不健康的架构。

错误分析

1.  **Monolithic Test Suite (单一巨石测试)**: 当您运行 `pytest packages/cascade-engine` 时，测试覆盖率报告显示它覆盖了 `cascade-sdk`, `cascade-graph`, `cascade-common` 等几乎所有包的代码。这证明了 `cascade-engine` 的测试正在导入并执行其他包的功能。这直接违反了我们之前重构的目标：**包的独立性和模块化**。

2.  **Incomplete Refactoring (不完整的重构)**: 上次的重构只移动了与 `engine` 无关的顶层测试。但是，`packages/cascade-engine/tests/` 目录内部仍然包含了本应属于其他包的测试。最明显的例子是：
    *   `packages/cascade-engine/tests/graph/`: 这里的所有测试都应该是 `cascade-graph` 包的一部分。
    *   `packages/cascade-engine/tests/connectors/test_local_connector.py`: 这个测试文件显然应该在 `cascade-connector-local` 包里。

3.  **"No Tests Ran" Mystery Solved**: 当您运行 `pytest packages/cascade-graph` 时，它报告 "collected 0 items"。这是因为 `packages/cascade-graph` 目录下根本**没有 `tests` 目录**！它的测试文件被错误地留在了 `cascade-engine` 包中。`cascade-connector-local` 和其他几个包也是同样的情况。

**结论**: 我们必须完成上次的重构，将 `cascade-engine` 中“寄生”的测试文件“遣返”到它们各自正确的包中，让每个包都能真正地独立测试。

我将创建一个计划来执行这次必要的“手术”。

## [WIP] refactor(tests): Decentralize monolithic engine test suite

### 错误分析
当前的测试结构存在一个严重的架构问题：`packages/cascade-engine/tests` 目录承担了对多个其他包（如 `cascade-graph`, `cascade-connector-local`）的测试职责，使其成为一个事实上的巨石型集成测试套件。这导致了两个主要问题：
1.  **违反模块化**: 其他包无法独立进行测试，因为它们的测试文件位于 `cascade-engine` 内部。
2.  **误导性的测试结果**: 运行 `pytest packages/cascade-graph` 等命令会报告“没有发现测试”，因为测试文件放错了位置。

测试覆盖率报告清晰地表明，`cascade-engine` 的测试套件正在不恰当地测试项目中的其他独立模块，这使得测试耦合性过高且难以维护。

### 用户需求
用户要求将 `cascade-engine` 测试套件中不属于它的测试迁移到各自正确的包中，以实现真正的模块化和独立的包测试。

### 评论
这是一个关键的架构修正。一个健康的 monorepo 项目，其核心优势之一就是能够独立地构建、测试和发布每一个包。将测试与其对应的源代码放在一起，是实现这一目标的基础。这次重构将彻底解决测试职责不清的问题，让每个包都成为一个完整、自洽的单元。

### 目标
1.  为那些还没有 `tests` 目录的包（如 `cascade-graph`, `cascade-connector-local`）创建 `tests` 目录。
2.  将 `packages/cascade-engine/tests/graph/` 目录下的所有测试文件移动到 `packages/cascade-graph/tests/`。
3.  将 `packages/cascade-engine/tests/connectors/test_local_connector.py` 文件移动到 `packages/cascade-connector-local/tests/`。

### 基本原理
此计划旨在完成测试与代码共存的重构。通过将测试文件精确地放置在它们所测试的源代码包中，我们确保了 `pytest packages/<package-name>` 这样的命令能够正确地发现并仅运行与该包相关的测试。这不仅修复了 "no tests ran" 的问题，更重要的是，它强制实施了清晰的架构边界，使得未来的开发和维护工作更加清晰和高效。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/brainstorm #task/domain/testing #task/object/test-suite #task/action/refactor #task/state/continue

---
### Script

#### Acts 1: 为缺失测试的包创建 `tests` 目录

首先，我们确保所有目标包都有一个 `tests` 目录。使用 `mkdir -p` 可以安全地创建目录，如果目录已存在也不会报错。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-graph/tests
mkdir -p packages/cascade-connector-local/tests
~~~~~

#### Acts 2: 迁移 `graph` 相关的测试

现在，我们将整个 `graph` 测试目录从 `engine` 移动到 `graph` 包。

~~~~~act
run_command
~~~~~
~~~~~
mv packages/cascade-engine/tests/graph/* packages/cascade-graph/tests/
rmdir packages/cascade-engine/tests/graph
~~~~~

#### Acts 3: 迁移 `local-connector` 相关的测试

最后，迁移 `local-connector` 的测试文件。

~~~~~act
run_command
~~~~~
~~~~~
mv packages/cascade-engine/tests/connectors/test_local_connector.py packages/cascade-connector-local/tests/
~~~~~

### 下一步建议

这次外科手术式的迁移是实现健康测试架构的最后一步。现在，您再次运行 `for i in (ls packages/); pytest packages/$i ; end` 循环时，应该会看到：
1.  `cascade-graph`, `cascade-connector-local` 等包现在能正确地发现并运行自己的测试。
2.  `cascade-engine` 的测试运行时长和覆盖率报告范围会显著减小，因为它只关心自己的代码。
3.  整个项目的测试覆盖率报告（当从根目录运行时）将是所有包独立覆盖率的真实总和。

我建议您立即运行 `pytest` 来验证所有测试是否仍在通过，并观察每个包的测试结果。
