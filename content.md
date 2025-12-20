That's an excellent and critical observation. Thank you for catching that. The appearance of question marks instead of colored blocks is a classic sign that the terminal is not correctly interpreting the ANSI escape codes being sent to it.

My previous implementation had a fundamental design flaw in how it integrated with the `rich` library.

## [WIP] fix(visualization): Use Rich-native styling instead of raw ANSI codes

### 错误分析
The root cause of the rendering issue is that I designed `palette.py` to generate raw ANSI escape code strings (e.g., `\033[38;2;255;255;200m`). Then, in `grid.py`, I incorrectly tried to inject these raw codes directly into `rich`'s markup language (e.g., `f"[\033[...]]██"`).

The `rich` library's markup parser does not interpret raw ANSI codes. It expects its own high-level style definitions, such as named colors (`"red"`), hex codes (`"#ff0000"`), or its own RGB syntax (`"rgb(255,0,0)"`). When `rich` encountered the raw escape codes inside the markup tags `[]`, it treated them as unknown characters, which the terminal then rendered as question marks (`?`).

The correct approach is to make the entire rendering pipeline speak `rich`'s language from start to finish.

### 用户需求
The terminal visualization must display colored grid cells as intended, without rendering garbage characters like question marks.

### 评论
This is a crucial bug fix that corrects a misunderstanding of the `rich` library's API. By migrating to `rich`'s native styling syntax, we are not just fixing a bug but are also making the code more idiomatic, readable, and robust. It properly leverages the abstraction layer that `rich` provides, instead of fighting against it.

### 目標
1.  Refactor `observatory/visualization/palette.py` to stop generating raw ANSI escape codes.
2.  The `Palettes` functions will now return `rich`-compatible style strings in the format `"rgb(r,g,b)"`.
3.  Ensure `GridView` correctly uses these new style strings to render the grid. (No change is actually needed in `grid.py` as it's already using the correct markup format `f"[{style}]..."`).

### 基本原理
The solution is to modify the `Palettes` class to produce strings that `rich` understands. Instead of building low-level escape codes like `\033[38;2;R;G;Bm`, we will build high-level style strings like `f"rgb({r},{g},{b})"`. The `GridView` component, which uses the format `f"[{style}]{char}"`, will then correctly interpret `"rgb(255,255,200)"` as a style instruction, and `rich` will handle the low-level conversion to the appropriate ANSI codes for the detected terminal type. This properly delegates the rendering responsibility to the library.

### 标签
#intent/fix #flow/ready #priority/critical #comp/cli #concept/ui #scope/dx #ai/instruct #task/domain/visualization #task/object/styling-integration #task/action/bug-fix #task/state/continue

---
### Script

#### Acts 1: Refactor `palette.py` to use `rich`-native RGB style strings

We will patch the `Palettes` class to output strings in the `rgb(r,g,b)` format, which is the correct way to specify TrueColor styles in `rich`.

~~~~~act
patch_file
observatory/visualization/palette.py
~~~~~
~~~~~python
    @staticmethod
    def firefly(brightness: np.ndarray) -> np.ndarray:
        """
        Maps 0.0-1.0 brightness to a Firefly gradient.
        0.0 (Refractory/Quiet) -> Dark Blue/Black
        0.5 (Charging) -> Deep Orange
        1.0 (Flash) -> Bright Yellow/White
        """
        # Initialize with Dark (Background)
        # \033[38;2;20;20;30m (Very Dark Blue)
        colors = np.full(brightness.shape, '\033[38;2;30;30;40m', dtype='<U24')
        
        # Low energy (Charging): Reddish
        mask_low = (brightness > 0.1) & (brightness <= 0.6)
        colors[mask_low] = '\033[38;2;100;40;40m'

        # High energy (Pre-flash): Orange
        mask_high = (brightness > 0.6) & (brightness <= 0.9)
        colors[mask_high] = '\033[38;2;200;120;0m'
        
        # Flash: Bright Yellow/White
        mask_flash = brightness > 0.9
        colors[mask_flash] = '\033[38;2;255;255;200m'
        
        return colors

    @staticmethod
    def bottleneck(states: np.ndarray) -> np.ndarray:
        """
        Maps states to bottleneck visualizer colors.
        0.0: Idle (Dim)
        0.5: Waiting (Cyan)
        1.0: Running (White/Green)
        """
        colors = np.full(states.shape, '\033[38;2;40;40;40m', dtype='<U24') # Dim Gray
        
        # Waiting (Cyan)
        mask_wait = (states > 0.4) & (states < 0.8)
        colors[mask_wait] = '\033[38;2;0;200;200m'
        
        # Running (Bright White/Green tint)
        mask_run = states >= 0.8
        colors[mask_run] = '\033[38;2;200;255;200m'
        
        return colors
~~~~~
~~~~~python
    @staticmethod
    def firefly(brightness: np.ndarray) -> np.ndarray:
        """
        Maps 0.0-1.0 brightness to a Firefly gradient using Rich-compatible styles.
        0.0 (Refractory/Quiet) -> Dark Blue/Black
        0.5 (Charging) -> Deep Orange
        1.0 (Flash) -> Bright Yellow/White
        """
        # Initialize with a dark background color in Rich's rgb format
        colors = np.full(brightness.shape, "rgb(30,30,40)", dtype="<U18")

        # Low energy (Charging): Reddish
        mask_low = (brightness > 0.1) & (brightness <= 0.6)
        colors[mask_low] = "rgb(100,40,40)"

        # High energy (Pre-flash): Orange
        mask_high = (brightness > 0.6) & (brightness <= 0.9)
        colors[mask_high] = "rgb(200,120,0)"

        # Flash: Bright Yellow/White
        mask_flash = brightness > 0.9
        colors[mask_flash] = "rgb(255,255,200)"

        return colors

    @staticmethod
    def bottleneck(states: np.ndarray) -> np.ndarray:
        """
        Maps states to bottleneck visualizer colors using Rich-compatible styles.
        0.0: Idle (Dim Gray)
        0.5: Waiting (Cyan)
        1.0: Running (Bright Green/White)
        """
        # Initialize with Dim Gray
        colors = np.full(states.shape, "rgb(40,40,40)", dtype="<U18")

        # Waiting (Cyan)
        mask_wait = (states > 0.4) & (states < 0.8)
        colors[mask_wait] = "rgb(0,200,200)"

        # Running (Bright Green/White tint)
        mask_run = states >= 0.8
        colors[mask_run] = "rgb(200,255,200)"

        return colors
~~~~~

### 下一步建议
The visualization system should now be fully functional and robust. Let's get back on track with the original plan:

1.  **Test**: Please run `python -m observatory.experiments.run_fireflies` again to confirm that the colors now render correctly.
2.  **Migrate**: Once confirmed, we will proceed with migrating `run_conway_experiment.py` and `bottleneck_sim.py` to this new, stable visualization framework.
3.  **Commit**: After all migrations are done, we will create a `[COMMIT]` plan to finalize this entire refactoring effort.
