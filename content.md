## [WIP] fix: 修复 MockConnector 主题匹配逻辑及 Engine 错误日志输出

### 错误分析
1.  **MockConnector 匹配逻辑错误**: `MockConnector` 使用简单的字典键值对查找 (`if topic in self.subscriptions`) 来匹配消息主题。然而，`Engine` 订阅的是通配符主题 `cascade/constraints/#`，而测试用例触发的是具体主题 `cascade/constraints/control`。由于这两个字符串不相等，回调函数从未被触发。
2.  **日志输出目标错误**: `Engine` 中的 `_on_constraint_update` 方法使用默认的 `print()` 函数，这会将信息输出到 `stdout`。而测试用例 `test_engine_handles_malformed_constraint_payload` 断言的是 `captured.err` (stderr)，导致断言失败。

### 用户需求
修复测试失败，确保 `Engine` 的约束同步机制能被正确验证。

### 评论
这是一个典型的测试工具实现细节导致的“伪失败”。修复它将验证我们的集成逻辑本身是正确的。

### 目标
1.  改进 `MockConnector` 的 `_trigger_message` 方法，实现对 `#` 通配符的基本支持。
2.  修改 `Engine` 的 `_on_constraint_update` 方法，使用 `sys.stderr` 作为输出目标。

### 基本原理
1.  **通配符匹配**: MQTT 的 `#` 通配符匹配该层级及以下的所有主题。简单的逻辑是：如果订阅了 `A/#`，那么发送到 `A/B` 的消息应该被匹配。
2.  **标准错误输出**: 错误日志理应输出到 `stderr`，这也符合测试框架捕获错误流的标准做法。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests #comp/runtime #concept/sync #scope/core
#ai/instruct
#task/domain/testing #task/object/mock-connector #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 Engine 的日志输出

将 `print` 调用修改为输出到 `sys.stderr`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
import time
import inspect
import asyncio
from typing import Any, Dict, Optional, Generator, Callable, List, Type
from uuid import uuid4
from contextlib import ExitStack
~~~~~
~~~~~python
import sys
import time
import inspect
import asyncio
from typing import Any, Dict, Optional, Generator, Callable, List, Type
from uuid import uuid4
from contextlib import ExitStack
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        except (KeyError, TypeError) as e:
            # In a real system, we'd use a proper logger.
            # For now, print to stderr to avoid crashing the engine.
            print(
                f"[Engine] Error processing constraint on topic '{topic}': {e}"
            )
~~~~~
~~~~~python
        except (KeyError, TypeError) as e:
            # In a real system, we'd use a proper logger.
            # For now, print to stderr to avoid crashing the engine.
            print(
                f"[Engine] Error processing constraint on topic '{topic}': {e}",
                file=sys.stderr,
            )
~~~~~

#### Acts 2: 改进 MockConnector 的匹配逻辑

修改 `test_engine_constraints.py` 中的 `MockConnector`，使其支持简单的后缀匹配。

~~~~~act
patch_file
packages/cascade-runtime/tests/runtime/test_engine_constraints.py
~~~~~
~~~~~python
    async def _trigger_message(self, topic: str, payload: Dict[str, Any]):
        """Helper to simulate receiving a message."""
        # Find a matching subscription (basic exact match for now)
        if topic in self.subscriptions:
            await self.subscriptions[topic](topic, payload)
~~~~~
~~~~~python
    async def _trigger_message(self, topic: str, payload: Dict[str, Any]):
        """Helper to simulate receiving a message."""
        # Check all subscriptions for a match
        for sub_topic, callback in self.subscriptions.items():
            is_match = False
            if sub_topic == topic:
                is_match = True
            elif sub_topic.endswith("/#"):
                prefix = sub_topic[:-2]
                if topic.startswith(prefix):
                    is_match = True
            
            if is_match:
                await callback(topic, payload)
~~~~~
