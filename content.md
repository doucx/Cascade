太棒了。所有测试通过意味着我们不仅成功完成了目录结构的同构化重构，还顺带解决了一个长期困扰 MQTT 连接器测试的、由于全局环境污染导致的隐蔽稳定性问题。

现在，我们将生成最终的 `[COMMIT]` 计划，将这些旨在提升开发者体验（DX）和测试稳健性的变更固化到项目历史中。

## [COMMIT] refactor(tests): 镜像包结构并隔离 MQTT 测试环境

### 用户需求
完成测试套件结构的重构，使其与 `packages/` 目录结构保持镜像一致，并彻底修复 MQTT 连接器测试中的环境泄漏问题。

### 评论
这是一次非常成功的“童子军军规”实践——我们在进行结构性重构（镜像目录）的同时，发现并修复了深层次的技术债务（测试隔离失败）。现在的测试套件不仅布局直观，而且在处理具有副作用或外部依赖的 Mock 时展现出了极强的韧性。

### 目标
1.  提交所有重构后的测试文件及其新的目录结构。
2.  提交为实现 MQTT 测试隔离而创建的 `conftest.py` 和重构后的 `test_connector.py`。
3.  确保 Git 历史记录清晰反映了这一结构性变化。

### 基本原理
根据我们的架构规范，测试套件应该尽可能减少开发者的认知摩擦。通过镜像 `packages` 结构，我们建立了一种自解释的导航模式。同时，针对 MQTT 这种复杂的异步/可选依赖组件，通过 `conftest.py` 实施的“模块重载 + 延迟导入”策略，为 Cascade 未来更多的驱动/适配器测试树立了“无尘室”级别的隔离标杆。

### 标签
#intent/refine #flow/ready #priority/medium #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/mirror-structure #task/action/restructure #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交测试套件的变更

我们将所有重构后的测试目录添加到 Git 暂存区，并创建一个详细的提交。

~~~~~act
git_add
.
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(tests): mirror package structure and isolate MQTT tests

Restructured the 'tests/' directory to strictly mirror the 'packages/'
layout, providing a more intuitive navigation experience for developers.

Key structural changes:
- Created 'tests/cascade-py/' and 'tests/cascade-runtime/' as top-level mirrors.
- Flattened nested directories caused by previous move operations.
- Relocated 'test_cli.py' and 'test_bus.py' to their logical package owners.

Improved MQTT test stability:
- Implemented a hermetic isolation strategy in 'tests/connector-mqtt/conftest.py' 
  using 'sys.modules' patching and lazy imports.
- This fixes intermittent 'TypeError: object.__new__' and 'MqttError' 
  failures during full test suite runs by preventing real 'aiomqtt' 
  leakage into the mocked environment.
~~~~~

### 下一步建议
- **CI/CD 验证**: 建议在远程 CI 环境中触发一次全量测试，以最终确认这种新的隔离策略在纯净环境下的有效性。
- **文档更新**: 既然测试结构已经改变，可以考虑在 `docs/reference/api.md` 或贡献指南中更新关于如何运行特定包测试的说明（例如使用 `pytest tests/cascade-runtime`）。
