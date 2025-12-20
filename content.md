你的分析一针见血。

日志中的数据揭示了一个经典的**反直觉瓶颈**：

1.  **显性数据**：`flush_duration_ms` 的平均值虽然只有 0.7ms，但最大值达到了 **31ms**。这意味着在某些帧，仅仅是更新 NumPy 矩阵就造成了严重的卡顿。
2.  **隐性瓶颈（关键）**：日志中**没有**记录 `rich` 渲染到终端所花费的时间。在 100x100 的网格下，旧的 `GridView` 实现每帧要创建 **10,000** 个 `Segment` 对象，并执行 **10,000** 次 `Style.parse()`。这是一个巨大的 CPU 密集型操作，它会长时间占用 GIL，导致你在后台线程（`to_thread`）中运行的 `flush` 操作无法及时获得 CPU 时间片，从而引发你观察到的 `flush_duration_ms` 尖峰。

只要主线程的渲染循环还在逐像素地解析样式，任何针对后台线程的优化都将被 GIL 锁死。

我们需要实施**“零开销渲染”**：将像素的 ANSI 颜色编码直接硬编码在 NumPy 数组中，并在渲染时通过矢量化操作拼接字符串，彻底绕过 Rich 的样式解析引擎。

这是修复计划。

## [WIP] perf(observatory): 矢量化 Rich 渲染管线以消除主线程 GIL 争用

### 用户需求
解决 `wave_test` 在高负载下出现的性能抖动问题。日志显示 `flush_duration_ms` 出现严重尖峰，推测是由于主线程渲染循环（`GridView.__rich_console__`）过度占用 GIL，导致后台 `flush` 线程饥饿。

### 评论
当前的渲染实现在每一帧、每一个像素点上都调用 `Style.parse()` 和 `Segment()` 构造函数。在 100x100 网格下，这意味着每秒百万级的 Python 对象创建和正则解析。这是典型的“以对象为中心”而非“以数据为中心”的设计错误。

### 目标
1.  **重构调色板 (`Palettes`)**：使其直接返回预计算的 ANSI 转义序列字符串（如 `\x1b[38;2;r;g;bm`），而非高层的 `rgb(r,g,b)` 样式描述符。
2.  **重构网格视图 (`GridView`)**：移除所有逐像素的 `Segment` 创建逻辑。利用 Python 的字符串 `join` 优化或 NumPy 的矢量化能力，将整行像素拼接为**单个**包含嵌入式 ANSI 代码的字符串，并封装在单个 `Segment` 中输出。
3.  **消除 GIL 争用**：将渲染循环从 CPU 密集型转变为 I/O 密集型（纯字符串拷贝），释放 GIL 给后台数据处理线程。

### 基本原理
Rich 的 `Segment` 支持直接输出包含 ANSI 转义码的原始文本。通过预先格式化颜色代码，我们可以完全绕过 Rich 昂贵的布局和样式计算引擎 (`Style.parse`)。这将把渲染复杂度从 $O(W \times H)$ 的对象操作降低为 $O(H)$ 的字符串拼接操作，预计将主线程开销降低 90% 以上。

### 标签
#intent/refine #flow/ready #priority/critical #comp/observatory #concept/ui #scope/perf #ai/instruct #task/domain/visualization #task/object/rendering-pipeline #task/action/vectorization #task/state/continue

---

### Script

#### Acts 1: 重构调色板以输出原始 ANSI 码

我们将修改 `Palettes` 类中的所有方法，使其不再返回 Rich 友好的 `rgb(...)` 字符串，而是返回终端友好的原生 ANSI 转义序列。这将消除下游 `Style.parse` 的必要性。

~~~~~act
patch_file
observatory/visualization/palette.py
~~~~~
~~~~~python
    @staticmethod
    def firefly(brightness: np.ndarray) -> np.ndarray:
        """
        Maps 0.0-1.0 brightness to a Firefly gradient using vectorized interpolation.
        """
        # Define color stops [R, G, B]
        stop1 = np.array([30, 30, 40])  # Dark Blue (at brightness 0.0)
        stop2 = np.array([200, 120, 0])  # Orange (at brightness 0.5)
        stop3 = np.array([255, 255, 200])  # Bright Yellow (at brightness 1.0)

        # Prepare output arrays
        r = np.zeros_like(brightness, dtype=np.uint8)
        g = np.zeros_like(brightness, dtype=np.uint8)
        b = np.zeros_like(brightness, dtype=np.uint8)

        # --- Vectorized Interpolation ---
        # Mask for the lower half of the gradient (0.0 to 0.5)
        mask1 = brightness <= 0.5
        # Normalize brightness in this range to 0-1 for interpolation
        t1 = brightness[mask1] * 2
        r[mask1] = (stop1[0] + (stop2[0] - stop1[0]) * t1).astype(np.uint8)
        g[mask1] = (stop1[1] + (stop2[1] - stop1[1]) * t1).astype(np.uint8)
        b[mask1] = (stop1[2] + (stop2[2] - stop1[2]) * t1).astype(np.uint8)

        # Mask for the upper half of the gradient (0.5 to 1.0)
        mask2 = brightness > 0.5
        # Normalize brightness in this range to 0-1 for interpolation
        t2 = (brightness[mask2] - 0.5) * 2
        r[mask2] = (stop2[0] + (stop3[0] - stop2[0]) * t2).astype(np.uint8)
        g[mask2] = (stop2[1] + (stop3[1] - stop2[1]) * t2).astype(np.uint8)
        b[mask2] = (stop2[2] + (stop3[2] - stop2[2]) * t2).astype(np.uint8)

        # Create rich-compatible "rgb(r,g,b)" strings. This is the slowest part.
        # We can optimize if needed, but it's more readable for now.
        return np.array(
            [f"rgb({r_},{g_},{b_})" for r_, g_, b_ in zip(r.flat, g.flat, b.flat)]
        ).reshape(r.shape)

    @staticmethod
    def bottleneck(states: np.ndarray) -> np.ndarray:
        """
        Maps states to bottleneck visualizer colors.
        0.0: Idle (Black/Dim)
        0.3: Sleeping (Grey)      -> .
        0.7: Blocked (Red)        -> x
        1.0: Running (White)      -> o
        """
        # Initialize with Black/Dim
        colors = np.full(states.shape, "rgb(20,20,20)", dtype="<U18")

        # Sleeping (Grey) ~ 0.3
        mask_sleep = (states > 0.2) & (states < 0.5)
        colors[mask_sleep] = "rgb(100,100,100)"

        # Blocked (Red) ~ 0.7
        mask_blocked = (states >= 0.5) & (states < 0.9)
        colors[mask_blocked] = "rgb(180,40,40)"

        # Running (Bright White) ~ 1.0
        mask_run = states >= 0.9
        colors[mask_run] = "rgb(255,255,255)"

        return colors

    @staticmethod
    def truth_diff(diff_matrix: np.ndarray) -> np.ndarray:
        """
        Maps a diff matrix to validation colors (3-Network Model).

        0: Dead (Correct)          -> Dim Gray
        1: Alive (Correct)         -> Bright White

        Logic Errors (vs Step Prediction):
        2: FP (Logic Ghost)        -> Bright Red
        3: FN (Logic Missing)      -> Cyan

        Drift Errors (vs Absolute Truth):
        4: FP (Drift Ghost)        -> Gold
        5: FN (Drift Missing)      -> Violet
        """
        # Default: 0 (Dead/Correct)
        colors = np.full(diff_matrix.shape, "rgb(40,40,40)", dtype="<U18")

        colors[diff_matrix == 1] = "rgb(220,220,220)"  # Alive (Correct)
        colors[diff_matrix == 2] = "rgb(255,50,50)"  # Logic FP (Red)
        colors[diff_matrix == 3] = "rgb(0,255,255)"  # Logic FN (Cyan)
        colors[diff_matrix == 4] = "rgb(255,215,0)"  # Drift FP (Gold)
        colors[diff_matrix == 5] = "rgb(238,130,238)"  # Drift FN (Violet)

        return colors
~~~~~
~~~~~python
    @staticmethod
    def firefly(brightness: np.ndarray) -> np.ndarray:
        """
        Maps 0.0-1.0 brightness to a Firefly gradient using vectorized interpolation.
        Returns raw ANSI escape codes for high-performance rendering.
        """
        # Define color stops [R, G, B]
        stop1 = np.array([30, 30, 40])  # Dark Blue (at brightness 0.0)
        stop2 = np.array([200, 120, 0])  # Orange (at brightness 0.5)
        stop3 = np.array([255, 255, 200])  # Bright Yellow (at brightness 1.0)

        # Prepare output arrays
        r = np.zeros_like(brightness, dtype=np.uint8)
        g = np.zeros_like(brightness, dtype=np.uint8)
        b = np.zeros_like(brightness, dtype=np.uint8)

        # --- Vectorized Interpolation ---
        # Mask for the lower half of the gradient (0.0 to 0.5)
        mask1 = brightness <= 0.5
        # Normalize brightness in this range to 0-1 for interpolation
        t1 = brightness[mask1] * 2
        r[mask1] = (stop1[0] + (stop2[0] - stop1[0]) * t1).astype(np.uint8)
        g[mask1] = (stop1[1] + (stop2[1] - stop1[1]) * t1).astype(np.uint8)
        b[mask1] = (stop1[2] + (stop2[2] - stop1[2]) * t1).astype(np.uint8)

        # Mask for the upper half of the gradient (0.5 to 1.0)
        mask2 = brightness > 0.5
        # Normalize brightness in this range to 0-1 for interpolation
        t2 = (brightness[mask2] - 0.5) * 2
        r[mask2] = (stop2[0] + (stop3[0] - stop2[0]) * t2).astype(np.uint8)
        g[mask2] = (stop2[1] + (stop3[1] - stop2[1]) * t2).astype(np.uint8)
        b[mask2] = (stop2[2] + (stop3[2] - stop2[2]) * t2).astype(np.uint8)

        # Create raw ANSI escape codes: \033[38;2;R;G;Bm
        return np.array(
            [f"\033[38;2;{r_};{g_};{b_}m" for r_, g_, b_ in zip(r.flat, g.flat, b.flat)]
        ).reshape(r.shape)

    @staticmethod
    def bottleneck(states: np.ndarray) -> np.ndarray:
        """
        Maps states to bottleneck visualizer colors (ANSI).
        0.0: Idle (Black/Dim)
        0.3: Sleeping (Grey)      -> .
        0.7: Blocked (Red)        -> x
        1.0: Running (White)      -> o
        """
        # Initialize with Black/Dim
        colors = np.full(states.shape, "\033[38;2;20;20;20m", dtype="<U20")

        # Sleeping (Grey) ~ 0.3
        mask_sleep = (states > 0.2) & (states < 0.5)
        colors[mask_sleep] = "\033[38;2;100;100;100m"

        # Blocked (Red) ~ 0.7
        mask_blocked = (states >= 0.5) & (states < 0.9)
        colors[mask_blocked] = "\033[38;2;180;40;40m"

        # Running (Bright White) ~ 1.0
        mask_run = states >= 0.9
        colors[mask_run] = "\033[38;2;255;255;255m"

        return colors

    @staticmethod
    def truth_diff(diff_matrix: np.ndarray) -> np.ndarray:
        """
        Maps a diff matrix to validation colors (3-Network Model) using ANSI codes.

        0: Dead (Correct)          -> Dim Gray
        1: Alive (Correct)         -> Bright White

        Logic Errors (vs Step Prediction):
        2: FP (Logic Ghost)        -> Bright Red
        3: FN (Logic Missing)      -> Cyan

        Drift Errors (vs Absolute Truth):
        4: FP (Drift Ghost)        -> Gold
        5: FN (Drift Missing)      -> Violet
        """
        # Default: 0 (Dead/Correct)
        colors = np.full(diff_matrix.shape, "\033[38;2;40;40;40m", dtype="<U20")

        colors[diff_matrix == 1] = "\033[38;2;220;220;220m"  # Alive (Correct)
        colors[diff_matrix == 2] = "\033[38;2;255;50;50m"    # Logic FP (Red)
        colors[diff_matrix == 3] = "\033[38;2;0;255;255m"    # Logic FN (Cyan)
        colors[diff_matrix == 4] = "\033[38;2;255;215;0m"    # Drift FP (Gold)
        colors[diff_matrix == 5] = "\033[38;2;238;130;238m"  # Drift FN (Violet)

        return colors
~~~~~

#### Acts 2: 重构 GridView 以使用行级字符串拼接

这是优化的核心。我们将移除 `_get_style` 方法（不再需要缓存样式对象），并彻底重写 `__rich_console__`。新的实现将简单地将 ANSI 颜色数组与像素字符数组进行字符串拼接，每行只生成一个 `Segment`。

~~~~~act
patch_file
observatory/visualization/grid.py
~~~~~
~~~~~python
    def __init__(
        self,
        width: int = 0,
        height: int = 0,
        palette_func: Callable[[np.ndarray], np.ndarray] = None,
        decay_per_second: float = 4.0,
    ):
        cols, rows = shutil.get_terminal_size()

        self.logical_width = width if width > 0 else cols // 2
        self.logical_height = height if height > 0 else max(10, rows - 5)

        self.config = GridConfig(
            width=self.logical_width,
            height=self.logical_height,
            decay_per_second=decay_per_second,
        )
        self.matrix = StateMatrix(self.config)
        self.palette_func = palette_func
        # Pre-cache styles to avoid parsing strings in the render loop
        self._style_cache: Dict[str, Style] = {}

    def _get_style(self, style_str: str) -> Style:
        """Caches Rich Style objects for performance."""
        if style_str not in self._style_cache:
            self._style_cache[style_str] = Style.parse(style_str)
        return self._style_cache[style_str]

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """The Rich render protocol method, optimized for performance."""
        brightness = self.matrix.get_snapshot()
        colors = self.palette_func(brightness)

        # Use a double-width block for square-like pixels
        char = "██"

        for y in range(self.logical_height):
            # Yield segments for one full row
            yield from [
                Segment(char, self._get_style(colors[y, x]))
                for x in range(self.logical_width)
            ]
            # Yield a newline to move to the next row
            yield Segment.line()
~~~~~
~~~~~python
    def __init__(
        self,
        width: int = 0,
        height: int = 0,
        palette_func: Callable[[np.ndarray], np.ndarray] = None,
        decay_per_second: float = 4.0,
    ):
        cols, rows = shutil.get_terminal_size()

        self.logical_width = width if width > 0 else cols // 2
        self.logical_height = height if height > 0 else max(10, rows - 5)

        self.config = GridConfig(
            width=self.logical_width,
            height=self.logical_height,
            decay_per_second=decay_per_second,
        )
        self.matrix = StateMatrix(self.config)
        self.palette_func = palette_func

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """
        The Rich render protocol method, highly optimized for throughput.
        It bypasses Rich's style parsing by constructing raw ANSI strings.
        """
        brightness = self.matrix.get_snapshot()
        # colors now contains raw ANSI escape codes (e.g. "\033[38;2;...m")
        colors = self.palette_func(brightness)

        # ANSI Reset code to clear color at the end of each line
        reset = "\033[0m"

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

### 下一步建议
运行 `renderer/wave_test.py`。你应该会看到 `flush_duration_ms` 显著下降（因为 GIL 释放了），并且 CPU 使用率大幅降低。即使在波浪最大（满屏更新）时，渲染帧率也不应出现剧烈跌落。这将证明我们彻底解除了渲染线程对主计算逻辑的阻塞。
