这是一个非常清晰的反馈。UI 冲突是因为“结果展示”和“加载进度”在竞争同一行屏幕空间。

我们将进行以下修正：
1.  **UI 分层**: 将“当前状态 (Sync/Error)”固定在第 N+1 行，将“加载进度 (Waiting)”下移至第 N+2 行。这样你可以同时看到上一代的验证结果和下一代的加载进度。
2.  **全局指标**: 在状态栏显式增加 `Total Errors` 计数。
3.  **随机初始化**: 替换滑翔机种子，改用 20% 密度的随机噪声初始化，这将产生更丰富的演化过程（虽然最终仍可能趋于稳定，但在 25x25 网格上会有更多动态）。

## [WIP] fix: 优化状态栏布局并启用随机初始化

### 错误分析
1.  **UI 竞争**: `render_waiting` 和 `update_frame` 都写入 `height + 1` 行，导致信息闪烁或覆盖。
2.  **演化单调**: 稀疏的滑翔机在小网格中容易撞墙或形成静态块（Block/Beehive）。

### 用户需求
1.  分离 WAITING 和 SYNC 的显示位置。
2.  增加全局失败计数。
3.  使用随机初始化。

### 目标
1.  修改 `renderer.py`：状态栏分两行。
2.  修改 `run_conway_experiment.py`：使用随机种子。

### 标签
#intent/tune #flow/ready #priority/medium #comp/cli #scope/ux #task/domain/visualization #task/object/renderer #task/action/polish

---

### Script

#### Acts 1: 优化渲染器布局 (renderer.py)

我们将状态信息分为两行：
-   Line 1: **[GEN: 10] ✅ SYNC | Total Err: 0** (结果层)
-   Line 2: **Wait: [██░░] 50/625** (进度层)

~~~~~act
patch_file
observatory/protoplasm/truth/renderer.py
~~~~~
~~~~~python
    def update_frame(self, gen: int, actual: np.ndarray, theoretical: np.ndarray, stats: dict):
        self._gen_counter = gen
        self._error_stats = stats
        self.matrix.update(actual, theoretical)
        self._render()

    def render_waiting(self, gen: int, current_count: int, total: int):
        """Updates only the status line to show loading progress."""
        self.driver.move_to(self.height + 1, 0)
        progress = current_count / total
        bar_len = 20
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        status = (
            f"GEN: {gen:<4} | "
            f"WAITING: [{bar}] {current_count}/{total} Agents | "
            f"Initializing..."
        )
        self.driver.write(f"{status:<80}")
        self.driver.flush()

    def _render(self):
~~~~~
~~~~~python
    def update_frame(self, gen: int, actual: np.ndarray, theoretical: np.ndarray, stats: dict):
        self._gen_counter = gen
        self._error_stats = stats
        self.matrix.update(actual, theoretical)
        self._render()

    def render_waiting(self, gen: int, current_count: int, total: int):
        """Updates only the progress line (Line 2) to show loading status."""
        # Move to Line 2 (height + 2)
        self.driver.move_to(self.height + 2, 0)
        
        progress = current_count / total if total > 0 else 0
        bar_len = 20
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        # Clear line first
        self.driver.write(f"{' ':<80}")
        self.driver.move_to(self.height + 2, 0)
        
        status = (
            f"Next Gen {gen}: [{bar}] {current_count}/{total}"
        )
        # Use dim color for waiting status
        self.driver.write(status, '\033[90m') 
        self.driver.flush()

    def _render(self):
~~~~~

~~~~~act
patch_file
observatory/protoplasm/truth/renderer.py
~~~~~
~~~~~python
        # 3. Status Line
        self.driver.move_to(self.height + 1, 0)
        status = (
            f"GEN: {self._gen_counter:<4} | "
            f"AbsErr: {self._error_stats['abs']:<4} | "
            f"RelErr: {self._error_stats['rel']:<4} | "
            f"Status: {'✅ SYNC' if self._error_stats['abs']==0 else '❌ DRIFT'}"
        )
        self.driver.write(f"{status:<80}")
        self.driver.flush()
~~~~~
~~~~~python
        # 3. Status Line (Line 1)
        self.driver.move_to(self.height + 1, 0)
        
        total_err = self._error_stats['abs'] + self._error_stats['rel']
        status_icon = "✅ SYNC" if total_err == 0 else "❌ DRIFT"
        
        status = (
            f"GEN: {self._gen_counter:<4} | "
            f"Status: {status_icon} | "
            f"Total Err: {total_err:<4} | "
            f"(Abs: {self._error_stats['abs']}, Rel: {self._error_stats['rel']})"
        )
        self.driver.write(f"{status:<80}")
        
        # Clear the waiting line (Line 2) because we just finished a frame
        self.driver.move_to(self.height + 2, 0)
        self.driver.write(f"{' ':<80}")
        
        self.driver.flush()
~~~~~

#### Acts 2: 启用随机初始化 (run_conway_experiment.py)

替换种子生成逻辑。

~~~~~act
patch_file
observatory/protoplasm/truth/run_conway_experiment.py
~~~~~
~~~~~python
def get_glider_seed(width: int, height: int) -> np.ndarray:
    """Creates a seeded grid with random gliders."""
    grid = np.zeros((height, width), dtype=np.int8)
    
    # Place a few gliders randomly
    num_gliders = max(1, (width * height) // 100)
    for _ in range(num_gliders):
        ox = random.randint(1, width - 4)
        oy = random.randint(1, height - 4)
        # Glider pattern
        grid[oy+0, ox+1] = 1
        grid[oy+1, ox+2] = 1
        grid[oy+2, ox+0:3] = 1
        
    return grid
~~~~~
~~~~~python
def get_random_seed(width: int, height: int, density: float = 0.2) -> np.ndarray:
    """Creates a grid initialized with random noise."""
    # Create a random float matrix 0.0-1.0
    rng = np.random.default_rng()
    noise = rng.random((height, width))
    # Threshold it to get binary state
    grid = (noise < density).astype(np.int8)
    return grid
~~~~~

~~~~~act
patch_file
observatory/protoplasm/truth/run_conway_experiment.py
~~~~~
~~~~~python
    # 4. Create Initial State
    initial_grid = get_glider_seed(GRID_WIDTH, GRID_HEIGHT)
    
    # 5. Build Agent Workflows
~~~~~
~~~~~python
    # 4. Create Initial State
    initial_grid = get_random_seed(GRID_WIDTH, GRID_HEIGHT, density=0.25)
    
    # 5. Build Agent Workflows
~~~~~

### 下一步建议
再次运行实验。现在你应该能看到：
1.  第一行清晰地显示当前代的同步状态。
2.  第二行在计算间隙显示数据收集进度，不再干扰第一行。
3.  网格充满了随机噪声，演化过程将更加生动和混乱。
