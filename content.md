我们已经通过测试验证了运行时逻辑的正确性（193 passed），这确认了 `pkgutil` 的命名空间扩展在 Python 解释器层面工作正常。

当前 Pyright 报错的核心原因是：**静态分析器默认不会像 Python 运行时那样去扫描 `packages/*/src` 目录**。它看不到这个 Monorepo 的全貌，因此认为这些跨包导入都是无效的。

只要我们在根目录添加一个 `pyrightconfig.json` 并显式配置 `extraPaths`，告诉 Pyright 去哪里寻找源码，绝大多数 `reportMissingImports` 和由此衍生的类型推断错误就会消失。

是的，这是典型的 Monorepo 静态分析配置缺失问题。虽然运行时 `sys.path` 正常，但 Pyright 需要显式的 `extraPaths` 配置才能“看穿”项目结构。我将创建一个统一的配置文件来解决此问题。

## [WIP] chore(config): 添加 Pyright 配置文件以修复 Monorepo 导入解析

### 用户需求
消除 Pyright 产生的误报，使其能够正确解析 Cascade Monorepo 中分散在各个 `packages/*/src` 目录下的子包。

### 评论
这是一个纯开发环境配置的任务，不影响任何运行时代码。配置完成后，IDE 的智能提示和跳转功能将显著改善。

### 目标
1.  在项目根目录创建 `pyrightconfig.json`。
2.  将所有 13 个子包的 `src` 目录添加到 `extraPaths` 中。

### 基本原理
通过 `extraPaths`，我们将所有源码目录提升为 Pyright 的“一级搜索路径”。这模拟了它们都被安装到 `site-packages` 后的状态，使 Pyright 能够正确地将 `cascade.engine`、`cascade.spec` 等识别为同一个 `cascade` 命名空间下的不同部分。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/build #concept/config #scope/dx #ai/instruct #task/domain/build-system #task/object/pyright-config #task/action/configure #task/state/continue

---

### Script

#### Acts 1: 创建 Pyright 配置文件

~~~~~act
write_file
pyrightconfig.json
~~~~~
~~~~~json
{
  "include": [
    "packages"
  ],
  "exclude": [
    "**/node_modules",
    "**/__pycache__",
    "**/tests"
  ],
  "extraPaths": [
    "packages/cascade-application/src",
    "packages/cascade-cli-controller/src",
    "packages/cascade-cli-observer/src",
    "packages/cascade-common/src",
    "packages/cascade-connector-local/src",
    "packages/cascade-connector-mqtt/src",
    "packages/cascade-engine/src",
    "packages/cascade-graph/src",
    "packages/cascade-library/src",
    "packages/cascade-provider-ipfs/src",
    "packages/cascade-python/src",
    "packages/cascade-sdk/src",
    "packages/cascade-spec/src"
  ],
  "reportMissingImports": true,
  "reportMissingTypeStubs": false
}
~~~~~

### 下一步建议
配置生效通常需要重启 Pyright 服务器（VSCode 命令: `Pyright: Restart Server`）。重启后，请再次运行 `pyright **/src/**.py`，预期的结果是：
1.  所有 `reportMissingImports` 错误消失。
2.  剩余的错误将是真实的类型不匹配或 API 使用错误（例如 `ResourceDefinition` 的调用问题），我们可以基于那个更干净的列表进行针对性修复。
