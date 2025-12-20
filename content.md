## [WIP] fix(demo): 修正 Matrix 渲染裁剪问题

分析显示，`observatory/visualization/matrix.py` 中的 `decay` 方法存在硬编码的 `np.clip(..., 0.0, 1.0)`。这导致我们的大于 1 的状态码（2=Red, 4=Gold, 5=Violet）全部被截断为 1.0（White）。这完美解释了为什么你看到了所有的结构，但它们全都是白色的。

我将修改 `StateMatrix` 的逻辑，使其支持更高的状态值范围。

#### Acts 1: 修正 Matrix 裁剪逻辑

~~~~~act
patch_file
observatory/visualization/matrix.py
~~~~~
~~~~~python
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
~~~~~python
    def decay(self, dt: float):
        """
        Applies time-based decay to the entire matrix.
        Optimized vectorized operation.
        
        Args:
            dt: The time delta in seconds since the last decay.
        """
        if self.cfg.decay_per_second > 0:
            decay_amount = self.cfg.decay_per_second * dt
            self.brightness -= decay_amount
            np.clip(self.brightness, 0.0, 1.0, out=self.brightness)
        # If decay is 0, we assume discrete state mode (e.g. Validator)
        # and do NOT clip to 1.0, allowing state codes like 2, 3, 4, 5 to persist.
~~~~~

### 下一步建议
再次运行 `python -m observatory.protoplasm.truth.truth_visualizer_demo`。这次你应该能看到绚丽的红、金、青、紫四色错误显示，彻底验证三网模型的有效性。
