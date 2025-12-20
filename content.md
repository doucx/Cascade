这是一个性能与逻辑并存的问题。

1.  **规模过载 (4000 Agents)**: 你的终端可能很大，导致自动计算出的网格（如 100x40）产生了 4000 个 Agent。在单线程的 `LocalExecutor` 加上 Python 的 `asyncio` 开销下，处理 4000 个高频交互的 Agent（每个都在订阅/发布/等待）会导致事件循环严重阻塞，表现为“死锁”或极度缓慢。
2.  **Gen 0 渲染缺失**: 验证器在 Gen 0 初始化时直接 `return` 并打印了日志，**跳过了渲染调用**。所以你没看到初始画面。
3.  **UI 闪烁**: `render_waiting` 和 `print` 混用导致输出混乱。

我们将大幅缩小规模以验证逻辑，并修复 Gen 0 的渲染路径。

## [WIP] fix: 缩减实验规模并修复 Gen 0 渲染缺失

### 错误分析
1.  **性能崩溃**: 4000 Agents 产生的并发消息量（4000 * 8 邻居 * N 代）压垮了 `LocalBus` 和 `asyncio` 循环。
2.  **逻辑漏洞**: `Validator._verify_generation` 中 Gen 0 的处理逻辑包含一个 `return`，导致它永远不会调用 `renderer.update_frame`。

### 用户需求
1.  能够看到动画。
2.  将 Agent 数量限制在安全范围（如 400 个）。

### 目标
1.  修改 `run_conway_experiment.py`，硬编码网格上限为 25x25。
2.  修改 `validator.py`，确保 Gen 0 也触发渲染更新。

### 标签
#intent/fix #intent/tune #flow/ready #priority/high #comp/tests #scope/core #task/domain/testing #task/object/experiment #task/action/downscale

---

### Script

#### Acts 1: 强制缩减实验规模 (run_conway_experiment.py)

我们将最大尺寸限制在 25x25 (625 Agents)，这是一个 `LocalExecutor` 可以轻松处理的数量。

~~~~~act
patch_file
observatory/protoplasm/truth/run_conway_experiment.py
~~~~~
~~~~~python
    # Ensure reasonable bounds
    GRID_WIDTH = min(GRID_WIDTH, 100) 
    GRID_HEIGHT = min(GRID_HEIGHT, 50)
    
    print(f"🚀 Starting Conway Experiment with grid {GRID_WIDTH}x{GRID_HEIGHT}...")
~~~~~
~~~~~python
    # Ensure reasonable bounds
    # Reduce to 25x25 to ensure LocalExecutor (single thread) can handle the message load smoothly
    GRID_WIDTH = min(GRID_WIDTH, 25) 
    GRID_HEIGHT = min(GRID_HEIGHT, 25)
    
    print(f"🚀 Starting Conway Experiment with grid {GRID_WIDTH}x{GRID_HEIGHT}...")
~~~~~

#### Acts 2: 修复 Gen 0 渲染逻辑 (validator.py)

去掉 Gen 0 的 `return`，并确保它正确设置 `actual_grid` 以便后续渲染。

~~~~~act
patch_file
observatory/protoplasm/truth/validator.py
~~~~~
~~~~~python
        # 2. Base Case: Gen 0
        if gen == 0:
            self.golden.seed(actual_grid)
            self.history_theoretical[0] = actual_grid
            print("🟦 [Gen 0] Axiom Set. System Initialized.")
            return
        
        # 3. Validation Logic
        
        # --- Check A: Absolute Truth (Trajectory) ---
~~~~~
~~~~~python
        # 2. Base Case: Gen 0
        if gen == 0:
            self.golden.seed(actual_grid)
            self.history_theoretical[0] = actual_grid
            # If renderer is active, we proceed to render Gen 0 instead of returning
            if not self.renderer:
                print("🟦 [Gen 0] Axiom Set. System Initialized.")
                return
            
            # Prepare dummy stats/grids for Gen 0 render
            theo_grid = actual_grid # Gen 0 is truth by definition
            is_absolute_match = True
            is_relative_match = True
            # Skip validation logic for Gen 0, fall through to reporting/rendering
        else:
            # 3. Validation Logic (Only for Gen > 0)
            
            # --- Check A: Absolute Truth (Trajectory) ---
~~~~~

~~~~~act
patch_file
observatory/protoplasm/truth/validator.py
~~~~~
~~~~~python
        # --- Check A: Absolute Truth (Trajectory) ---
        # Did we stay on the path defined by T0?
        prev_theo = self.history_theoretical.get(gen - 1)
        is_absolute_match = False
        
        if prev_theo is not None:
            self.golden.seed(prev_theo)
            theo_grid = self.golden.step()
            self.history_theoretical[gen] = theo_grid
            
            diff_abs = np.sum(actual_grid != theo_grid)
            if diff_abs == 0:
                is_absolute_match = True
            else:
                self.absolute_errors += diff_abs
        else:
            # Should not happen if processing in order
            print(f"⚠️  Missing history for Absolute check at Gen {gen}")

        # --- Check B: Relative Truth (Transition) ---
        # Did we calculate correctly based on what we had yesterday?
        prev_actual = self.history_actual.get(gen - 1)
        is_relative_match = False
        
        if prev_actual is not None:
            self.golden.seed(prev_actual)
            expected_relative = self.golden.step()
            
            diff_rel = np.sum(actual_grid != expected_relative)
            if diff_rel == 0:
                is_relative_match = True
            else:
                self.relative_errors += diff_rel
        else:
             print(f"⚠️  Missing history for Relative check at Gen {gen}")

        # 4. Reporting
~~~~~
~~~~~python
            # --- Check A: Absolute Truth (Trajectory) ---
            # Did we stay on the path defined by T0?
            prev_theo = self.history_theoretical.get(gen - 1)
            is_absolute_match = False
            
            # Default to actual if we can't compute theory (error case)
            theo_grid = actual_grid 
            
            if prev_theo is not None:
                self.golden.seed(prev_theo)
                theo_grid = self.golden.step()
                self.history_theoretical[gen] = theo_grid
                
                diff_abs = np.sum(actual_grid != theo_grid)
                if diff_abs == 0:
                    is_absolute_match = True
                else:
                    self.absolute_errors += diff_abs
            else:
                # Should not happen if processing in order
                print(f"⚠️  Missing history for Absolute check at Gen {gen}")

            # --- Check B: Relative Truth (Transition) ---
            # Did we calculate correctly based on what we had yesterday?
            prev_actual = self.history_actual.get(gen - 1)
            is_relative_match = False
            
            if prev_actual is not None:
                self.golden.seed(prev_actual)
                expected_relative = self.golden.step()
                
                diff_rel = np.sum(actual_grid != expected_relative)
                if diff_rel == 0:
                    is_relative_match = True
                else:
                    self.relative_errors += diff_rel
            else:
                 print(f"⚠️  Missing history for Relative check at Gen {gen}")

        # 4. Reporting
~~~~~

### 下一步建议
再次运行 `python -m observatory.protoplasm.truth.run_conway_experiment`。

这次 Agent 数量应该是 ~600，Gen 0 应该会立即显示，随后你会看到生命游戏的演化。

如果依然“看起来”卡顿，请注意 `WAITING` 进度条是否在移动。如果是，说明计算正在进行，只是比较慢（Python 处理大量 Future 的开销）。只要它在动，就证明逻辑是通的。
