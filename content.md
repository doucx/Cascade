好的，我们已经验证了核心逻辑，现在是时候进行“像素打磨”了。你说得对，终端字符的宽高比是美学上的一个关键障碍，我们将用经典的“双字符单元格”技术来解决它，并完全转向以颜色为核心的视觉语言。

我将生成一个计划来执行这些美学优化。

## [WIP] tune: 优化渲染单元格为方形并改进颜色方案

### 用户需求
1.  **方形单元格**: 将渲染的单元格从单个字符（如 `#`）改为两个字符（如 `██`），使其在视觉上接近方形。
2.  **颜色驱动**: 使用统一的块字符 `█`，并通过颜色来区分所有状态（活/死/错误）。
3.  **随机种子**: 确保实验使用随机初始状态，以获得更有趣的视觉效果。

### 评论
这是从“功能可用”到“体验良好”的关键一步。采用方形单元格和纯色编码将大大提升可视化的清晰度和专业感。

### 目标
1.  修改 `run_conway_experiment.py`，调整逻辑网格宽度的计算方式，以适应物理上双倍的渲染宽度。
2.  修改 `renderer.py`，实现将一个逻辑单元格渲染为两个物理字符，并更新颜色方案以提高对比度和清晰度。

### 基本原理
-   **双字符渲染**: 终端字符通常高是宽的两倍。通过将一个逻辑像素渲染为 `██`，我们可以在视觉上创造一个近似 1:1 的宽高比。
-   **矢量化更新**: 为保持性能，我们将使用 `numpy.repeat` 将逻辑状态矩阵（例如 `25x25`）高效地扩展为物理渲染矩阵（`25x50`），然后进行矢量化的字符和颜色赋值。

### 标签
#intent/tune #flow/ready #priority/medium #comp/cli #scope/ux #task/domain/visualization #task/object/renderer #task/action/polish #task/state/end

---

### Script

#### Acts 1: 调整实验脚本以适应更宽的渲染区

我们需要将逻辑网格宽度减半，因为每个单元格现在需要两个字符的物理空间。

~~~~~act
patch_file
observatory/protoplasm/truth/run_conway_experiment.py
~~~~~
~~~~~python
    # Auto-detect terminal size to fit the grid
    cols, rows = shutil.get_terminal_size()
    # Leave room for logs and status lines
    GRID_WIDTH = cols
    GRID_HEIGHT = rows - 6 
    
    # Ensure reasonable bounds
    # Reduce to 25x25 to ensure LocalExecutor (single thread) can handle the message load smoothly
    GRID_WIDTH = min(GRID_WIDTH, 25) 
    GRID_HEIGHT = min(GRID_HEIGHT, 25)
~~~~~
~~~~~python
    # Auto-detect terminal size to fit the grid
    cols, rows = shutil.get_terminal_size()
    # Leave room for logs and status lines
    # Each cell is 2 chars wide, so logical width is half the terminal width
    GRID_WIDTH = cols // 2
    GRID_HEIGHT = rows - 4 # We only need 2 status lines now
    
    # Ensure reasonable bounds for performance
    GRID_WIDTH = min(GRID_WIDTH, 50) 
    GRID_HEIGHT = min(GRID_HEIGHT, 25)
~~~~~

#### Acts 2: 更新渲染器以支持方形单元格和新颜色方案

我们将修改 `TruthRenderer` 的 `__init__` 和 `_render` 方法。

**Step 1: 更新构造函数以创建双倍宽度的缓冲区**

~~~~~act
patch_file
observatory/protoplasm/truth/renderer.py
~~~~~
~~~~~python
    def __init__(self, width: int = 20, height: int = 20):
        self.width = width
        self.height = height
        self.matrix = DiffMatrix(width, height)
        
        self.buffer_prev = RenderBuffer(width, height)
        self.buffer_curr = RenderBuffer(width, height)
        self.driver = AnsiDriver()
~~~~~
~~~~~python
    def __init__(self, width: int = 20, height: int = 20):
        self.width = width
        self.height = height
        self.matrix = DiffMatrix(width, height)
        
        # Physical buffers are twice the logical width for square cells
        self.buffer_prev = RenderBuffer(width * 2, height)
        self.buffer_curr = RenderBuffer(width * 2, height)
        self.driver = AnsiDriver()
~~~~~

**Step 2: 重写核心渲染逻辑**

~~~~~act
patch_file
observatory/protoplasm/truth/renderer.py
~~~~~
~~~~~python
    def _render(self):
        # 1. Rasterize Matrix to Buffer
        self.buffer_curr.chars[:] = ' '
        self.buffer_curr.colors[:] = ''
        
        grid = self.matrix.grid
        
        # Match Alive: White '#'
        mask_match = grid == 1
        self.buffer_curr.chars[mask_match] = '#'
        self.buffer_curr.colors[mask_match] = '\033[97m' # Bright White
        
        # Match Dead: Dim '.'
        mask_dead = grid == 0
        self.buffer_curr.chars[mask_dead] = '.'
        self.buffer_curr.colors[mask_dead] = '\033[90m' # Dark Gray
        
        # False Positive: Red 'X'
        mask_fp = grid == 2
        self.buffer_curr.chars[mask_fp] = 'X'
        self.buffer_curr.colors[mask_fp] = '\033[91m' # Bright Red
        
        # False Negative: Cyan 'O'
        mask_fn = grid == 3
        self.buffer_curr.chars[mask_fn] = 'O'
        self.buffer_curr.colors[mask_fn] = '\033[96m' # Bright Cyan

        # 2. Diff & Draw
        rows, cols = RenderBuffer.compute_diff(self.buffer_prev, self.buffer_curr)
~~~~~
~~~~~python
    def _render(self):
        # 1. Rasterize Matrix to Buffer using vectorized operations
        
        # Logical grid (e.g., 25x50)
        logical_grid = self.matrix.grid

        # Create physical masks by repeating columns (e.g., creates a 25x100 mask)
        phys_mask_alive = np.repeat(logical_grid == 1, 2, axis=1)
        phys_mask_dead = np.repeat(logical_grid == 0, 2, axis=1)
        phys_mask_fp = np.repeat(logical_grid == 2, 2, axis=1)
        phys_mask_fn = np.repeat(logical_grid == 3, 2, axis=1)

        # Apply character (always a block)
        self.buffer_curr.chars[:] = '█'

        # Apply colors based on physical masks
        self.buffer_curr.colors[phys_mask_alive] = '\033[97m' # Bright White
        self.buffer_curr.colors[phys_mask_dead] = '\033[90m'  # Dark Gray
        self.buffer_curr.colors[phys_mask_fp] = '\033[91m'    # Bright Red
        self.buffer_curr.colors[phys_mask_fn] = '\033[96m'   # Bright Cyan

        # 2. Diff & Draw
        rows, cols = RenderBuffer.compute_diff(self.buffer_prev, self.buffer_curr)
~~~~~
