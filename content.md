# [WIP] fix: 修复 TelemetrySubscriber 中缺失的 asyncio 导入

## 摘要

本计划修复了 `TelemetrySubscriber` 模块中因缺少 `import asyncio` 而导致的 `NameError`。这是导致 `workflow_demo.py` 运行时崩溃的直接原因。

## 错误分析

### 1. `NameError: name 'asyncio' is not defined`
*   **原因**: 在将 `on_event` 方法重构为同步方法并使用 `asyncio.create_task` 进行异步调度时，我在 `packages/cascade-runtime/src/cascade/runtime/subscribers.py` 文件头部遗漏了 `import asyncio` 语句。
*   **影响**: 任何启用了连接器（Connector）的工作流在尝试发送遥测数据时都会崩溃。
*   **解决方案**: 在文件顶部添加缺失的导入语句。

## 用户需求
1.  使 `workflow_demo.py` 能够正常运行，不报错。

## 评论
这是一个简单的遗漏，但阻碍了功能的验证。修复后，系统应能完整运行。

## 目标
1.  在 `subscribers.py` 中导入 `asyncio`。

## 基本原理
Python 需要显式导入模块才能使用。

## 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #scope/core #ai/instruct #task/domain/telemetry #task/object/subscriber #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 添加缺失的导入

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
import platform
import os
from datetime import datetime, timezone
from .bus import MessageBus
from cascade.common.messaging import bus
from .events import (
~~~~~
~~~~~python
import platform
import os
import asyncio
from datetime import datetime, timezone
from .bus import MessageBus
from cascade.common.messaging import bus
from .events import (
~~~~~

### 下一步建议
应用此修复后，请再次运行 `python workflow_demo.py`。如果一切正常（看到日志输出且无崩溃），我们将生成一个 `[COMMIT]` 计划来保存这些重要的修复。
