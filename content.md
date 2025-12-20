您的洞察力非常敏锐，完全正确。您已经精确地诊断出了问题的核心：**我的衰减逻辑与帧率（FPS）紧密耦合，而不是与真实世界的时间解耦。**

这是一个典型的新手在游戏或模拟开发中会犯的错误。当FPS飙升到800时，每秒会执行800次衰减，导致亮度在`1 / (800 * 0.1)`约等于12毫秒内就耗尽了，这当然看起来只是“闪了一下”。

我为这个疏忽道歉。我们需要立刻修正这个物理模型，使其基于**时间增量（delta time, `dt`）**进行计算，这样无论帧率是30 FPS还是800 FPS，余晖的视觉持续时间都将是恒定的。

## [WIP] fix(visualization): Decouple visual decay from frame rate for consistent effects

### 错误分析
用户反馈指出，尽管FPS提高了，但视觉效果（特别是余晖）变得不自然且过快。根本原因在于 `StateMatrix.decay()` 方法的实现是基于帧的，每次调用都会减去一个固定的`decay_rate`。这导致衰减速度与渲染循环的执行频率（FPS）成正比。在高FPS下，衰减过程被极度压缩，无法形成平滑、持续的视觉效果。

正确的物理模拟必须基于流逝的真实时间。衰减量应该是 `每秒衰减率 * 帧间流逝时间(dt)`。

### 用户需求
1.  余晖效果必须是平滑的，并且其持续时间应与真实世界时间挂钩（例如，从最亮到最暗持续约0.2-0.5秒），不受FPS波动的影响。
2.  应用应保持高性能。

### 评论
这是一个至关重要的修复，它将我们的可视化工具从一个简单的“动画播放器”提升为一个具备基本物理一致性的“模拟器”。实现帧率无关的物理更新是所有动态视觉系统的基石。这次修复将使我们的“创世开发包”更加健壮和可预测。

### 目标
1.  **修改 `StateMatrix`**: `decay` 方法将接受一个`dt` (delta time，浮点数，表示自上一帧以来经过的秒数) 参数。
2.  **修改 `GridConfig`**: 将 `decay_rate` 重命名为 `decay_per_second`，以更清晰地反映其含义，并为其设定一个基于时间的新默认值（例如`4.0`，意味着亮度在0.25秒内从1.0衰减到0）。
3.  **更新 `TerminalApp`**: 在渲染循环中，计算每帧的`dt`，并将其传递给`grid_view.matrix.decay(dt)`。
4.  **更新调用点**: 修改 `run_fireflies.py` 和 `GridView` 的初始化，使用新的 `decay_per_second` 参数。

### 基本原理
我们将把衰减计算从 `brightness -= rate` 改为 `brightness -= rate_per_second * dt`。
-   `rate_per_second`: 是一个常数，定义了“亮度每秒下降多少”。
-   `dt`: 是一个变量，即 `current_time - last_frame_time`。

这样，如果FPS高（`dt`很小），每次衰减的量就小；如果FPS低（`dt`很大），每次衰减的量就大。最终，总的衰减速度在真实时间维度上保持恒定，从而实现了帧率解耦。

### 标签
#intent/fix #intent/refine #flow/ready #priority/high #comp/cli #concept/ui #task/domain/visualization #task/object/physics-simulation #task/action/decoupling #task/state/continue

---
### Script

#### Acts 1: Update `StateMatrix` to be time-based

我们首先修改 `matrix.py`，让 `decay` 方法接受 `dt` 参数，并更新配置。

~~~~~act
patch_file
observatory/visualization/matrix.py
~~~~~
~~~~~python
@dataclass
class GridConfig:
    width: int = 100
    height: int = 100
    decay_rate: float = 0.1

class StateMatrix:
    """
    Manages the 'physics' of the grid:
    - Logical state (is the agent active?)
    - Physical state (brightness/afterglow)
    """

    def __init__(self, config: GridConfig):
        self.cfg = config
        # brightness: Float 0.0 - 1.0 (1.0 = Flash, 0.0 = Dark)
        self.brightness = np.zeros((self.cfg.height, self.cfg.width), dtype=np.float32)
        # active: Boolean (True = Agent exists/alive)
        self.active = np.zeros((self.cfg.height, self.cfg.width), dtype=bool)

    def update(self, x: int, y: int, state: float):
        """
        Updates the state of a single cell.
        state: 1.0 usually indicates a flash trigger.
        """
        if 0 <= x < self.cfg.width and 0 <= y < self.cfg.height:
            self.brightness[y, x] = state
            self.active[y, x] = True

    def decay(self):
        """
        Applies decay to the entire matrix.
        Optimized vectorized operation.
        """
        # Subtract decay_rate, clip at 0.0
        self.brightness -= self.cfg.decay_rate
        np.clip(self.brightness, 0.0, 1.0, out=self.brightness)
~~~~~
~~~~~python
@dataclass
class GridConfig:
    width: int = 100
    height: int = 100
    decay_per_second: float = 4.0 # Brightness fades from 1.0 to 0 in 0.25s

class StateMatrix:
    """
    Manages the 'physics' of the grid:
    - Logical state (is the agent active?)
    - Physical state (brightness/afterglow)
    """

    def __init__(self, config: GridConfig):
        self.cfg = config
        # brightness: Float 0.0 - 1.0 (1.0 = Flash, 0.0 = Dark)
        self.brightness = np.zeros((self.cfg.height, self.cfg.width), dtype=np.float32)
        # active: Boolean (True = Agent exists/alive)
        self.active = np.zeros((self.cfg.height, self.cfg.width), dtype=bool)

    def update(self, x: int, y: int, state: float):
        """
        Updates the state of a single cell.
        state: 1.0 usually indicates a flash trigger.
        """
        if 0 <= x < self.cfg.width and 0 <= y < self.cfg.height:
            self.brightness[y, x] = state
            self.active[y, x] = True

    def decay(self, dt: float):
        """
        Applies time-based decay to the entire matrix.
        Optimized vectorized operation.
        
        Args:
            dt: The time delta in seconds since the last decay.
        """
        decay_amount = self.cfg.decay_per_second * dt
        self.brightness -= decay_amount
        np.clip(self.brightness, 0.0, 1.0, out=self.brightness)
~~~~~

#### Acts 2: Update `GridView` to use the new parameter name

现在我们更新 `grid.py` 以使用 `decay_per_second`。

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
        decay_rate: float = 0.05
    ):
        cols, rows = shutil.get_terminal_size()
        
        self.logical_width = width if width > 0 else cols // 2
        self.logical_height = height if height > 0 else max(10, rows - 5)
        
        self.config = GridConfig(
            width=self.logical_width, 
            height=self.logical_height, 
            decay_rate=decay_rate
        )
~~~~~
~~~~~python
    def __init__(
        self,
        width: int = 0,
        height: int = 0,
        palette_func: Callable[[np.ndarray], np.ndarray] = None,
        decay_per_second: float = 4.0
    ):
        cols, rows = shutil.get_terminal_size()
        
        self.logical_width = width if width > 0 else cols // 2
        self.logical_height = height if height > 0 else max(10, rows - 5)
        
        self.config = GridConfig(
            width=self.logical_width, 
            height=self.logical_height, 
            decay_per_second=decay_per_second
        )
~~~~~

#### Acts 3: Update `TerminalApp` to pass `dt` to the decay function

这是核心修复。我们在 `app.py` 的渲染循环中计算 `frame_time` (即 `dt`) 并将其传递下去。

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~python
                # Apply physics/decay to the grid
                self.grid_view.matrix.decay()

                # Calculate FPS using a moving average of last 10 frames
~~~~~
~~~~~python
                # Calculate dt (frame_time) for physics update
                now = time.perf_counter()
                frame_time = now - last_time
                last_time = now

                # Apply physics/decay to the grid using the calculated dt
                self.grid_view.matrix.decay(frame_time)

                # Calculate FPS using a moving average of last 10 frames
~~~~~
~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~python
                # Calculate FPS using a moving average of last 10 frames
                now = time.perf_counter()
                frame_time = now - last_time
                last_time = now
                frame_times.append(frame_time)
~~~~~
~~~~~python
                frame_times.append(frame_time)
~~~~~

#### Acts 4: Update `run_fireflies.py` to use the new decay parameter

最后，确保实验脚本使用新的、基于时间的参数来实例化`GridView`。我们将衰减率设置为 `5.0`，这意味着余晖效果将在 `1.0 / 5.0 = 0.2` 秒内完成。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
        # 1. Create visualization components
        grid_view = GridView(width=grid_width, height=grid_width, palette_func=Palettes.firefly, decay_rate=0.1)
        status_bar = StatusBar(initial_status={"Agents": num_agents, "Sync (R)": "Initializing..."})
~~~~~
~~~~~python
        # 1. Create visualization components
        # A decay_per_second of 5.0 means a flash will fade in 1/5 = 0.2 seconds.
        grid_view = GridView(width=grid_width, height=grid_width, palette_func=Palettes.firefly, decay_per_second=5.0)
        status_bar = StatusBar(initial_status={"Agents": num_agents, "Sync (R)": "Initializing..."})
~~~~~

### 下一步建议
请再次运行 `python -m observatory.experiments.run_fireflies`。现在，无论FPS如何变化，您都应该能观察到一个持续时间稳定、平滑渐变的余晖效果。如果觉得0.2秒的衰减时间太快或太慢，只需调整 `run_fireflies.py` 中 `decay_per_second` 的值即可轻松控制。

一旦您对效果满意，我们就可以继续将其他实验迁移到这个现在已经非常健壮的可视化框架上了。
