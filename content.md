## [WIP] refactor: Consolidate and clarify integration test structure

### 用户需求
用户要求识别任何在重构后仍然位置不当的测试，并提出一个计划来优化其结构，以提高项目的清晰度和可维护性。

### 评论
这是一个非常有价值的整理步骤。在大型重构之后，进行一次“细粒度”的调整可以巩固成果，并确保项目遵循一致、清晰的架构原则。清理冗余的目录结构将改善开发者的体验，并使测试的意图更加明确。

### 目标
1.  将位于 `tests/e2e/e2e/` 目录下的 E2E 测试文件移动到其父目录 `tests/e2e/`。
2.  删除现在已经为空的 `tests/e2e/e2e` 目录。

### 基本原理
顶级 `tests` 目录的目的是存放跨越多个内部包的集成（Integration）和端到端（E2E）测试。当前的 `tests/e2e/e2e` 结构是多余的。通过将测试文件提升一级到 `tests/e2e/`，我们创建了一个更扁平、更直观的结构，这使得定位和理解这些高阶测试变得更加容易。

### 标签
#intent/refine #flow/ready #priority/medium #comp/tests #scope/dx #ai/brainstorm #task/domain/testing #task/object/directory-structure #task/action/refactor #task/state/end

---
### Script

#### Acts 1: 移动 E2E 测试并清理目录

我们将把 E2E 测试文件上移一级，然后删除多余的空目录。

~~~~~act
run_command
~~~~~
~~~~~
mv tests/e2e/e2e/* tests/e2e/
rmdir tests/e2e/e2e
~~~~~

### 下一步建议

我们已经完成了对测试结构的最终整理。现在，项目在单元测试、包内集成测试和跨包 E2E 测试之间有了清晰的界限。

-   **Unit & Integration Tests**: 位于各自的 `packages/*/tests/` 目录下。
-   **E2E & Contract Tests**: 位于顶级的 `tests/` 目录下。

我建议最后运行一次完整的测试套件，以确保所有测试（包括移动后的 E2E 测试）都能被 `pytest` 正确发现并成功执行。

`pytest`
