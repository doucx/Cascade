非常感谢你的详细反馈。这个现象（`[38;2...` 残留 + 局部渲染）证实了我的推测：**Rich 正在对包含 ANSI 码的长字符串进行自动换行**。

**故障分析**：
1.  我们生成的 `row_content` 是一个包含大量 ANSI 码的巨型字符串。
2.  尽管其“视觉长度”可能只有 200 个字符（100个像素 x 2），但其“物理长度”可能有 2000+ 字符（每个 ANSI 码占 ~20 字符）。
3.  Rich 的 `Segment(text)` 默认会将 `text` 视为可打印内容，并根据 `Console` 的宽度（例如 100 列）进行强制换行。
4.  当换行点不幸落在 ANSI 转义序列（如 `\033[38;...`）的中间时，转义序列被打断，导致终端无法识别颜色，从而打印出乱码 `[38;2...`。
5.  同时，由于强制换行，一行像素被拆成了几十行输出，导致屏幕瞬间被填满，只能看到左上角的一小部分逻辑网格。

**修复方案**：
我们需要使用 `rich.control.Control` 而非 `rich.segment.Segment`。
*   `Segment` 用于文本，Rich 会计算其宽度并进行排版（换行、截断）。
*   `Control` 用于控制码（如光标移动、颜色），Rich 会将其视为**零宽度**并直接透传给终端，**不做任何换行处理**。

这将完美解决乱码和布局错乱问题，同时保留我们刚刚获得的巨大性能提升。

## [WIP] fix(observatory): 使用 Rich Control 封装原始 ANSI 流以防止自动换行破坏

### 用户需求
修复 `wave_test` 中的渲染乱码和布局崩溃问题。保持高性能的 ANSI 拼接策略，但阻止 Rich 对 ANSI 字符串进行错误的宽度计算和自动换行。

### 评论
这是一个经典抽象泄漏问题。我们试图绕过 Rich 的样式系统直接输出 ANSI，但错误地将其包装在了受 Rich 排版引擎管理的 `Segment` 中。将其切换为 `Control` 对象将告诉 Rich：“这是原始指令流，不要触碰，直接发送。”

### 目标
修改 `GridView.__rich_console__`，将拼接好的行字符串封装在 `rich.control.Control` 对象中返回。

### 标签
#intent/fix #flow/ready #priority/critical #comp/observatory #concept/ui #scope/bugfix #ai/instruct #task/domain/visualization #task/object/rendering-pipeline #task/action/wrap-control #task/state/continue

---

### Script

#### Acts 1: 引入 `Control` 并替换 `Segment`

~~~~~act
patch_file
observatory/visualization/grid.py
~~~~~
~~~~~python
import numpy as np
import shutil
from typing import Callable

from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment
from rich.style import Style

# Re-using the matrix logic from protoplasm as it's solid
~~~~~
~~~~~python
import numpy as np
import shutil
from typing import Callable

from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment
from rich.control import Control
from rich.style import Style

# Re-using the matrix logic from protoplasm as it's solid
~~~~~

~~~~~act
patch_file
observatory/visualization/grid.py
~~~~~
~~~~~python
        # Vectorized string construction.
        # We iterate over rows and join the (color + block) strings.
        # This is significantly faster than creating 10,000 Segment objects.
        for y in range(self.logical_height):
            # Join all columns in this row: color_code + "██"
            # Since `colors` is a numpy array of strings, this loop is tight.
            row_content = "".join(f"{code}██" for code in colors[y])
            
            # Yield a single Segment for the entire row, plus the reset code.
            # Rich will output this raw text directly to the terminal.
            yield Segment(row_content + reset)
            yield Segment.line()
~~~~~
~~~~~python
        # Vectorized string construction.
        # We iterate over rows and join the (color + block) strings.
        # This is significantly faster than creating 10,000 Segment objects.
        for y in range(self.logical_height):
            # Join all columns in this row: color_code + "██"
            # Since `colors` is a numpy array of strings, this loop is tight.
            row_content = "".join(f"{code}██" for code in colors[y])
            
            # Yield a Control object.
            # Rich treats Control objects as having 0 width and does NOT wrap them.
            # This allows our long ANSI string to pass through to the terminal intact.
            yield Control(row_content + reset)
            yield Segment.line()
~~~~~

### 下一步建议
再次运行 `renderer/wave_test.py`。
这次你应该看到：
1.  **完美的布局**：网格整齐地填充在上方，没有乱码。
2.  **极致的性能**：FPS 保持高位，`flush_duration_ms` 保持微秒级。
3.  **无残影**：ANSI 码被正确解析，颜色正确显示。
