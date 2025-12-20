这是一个快速的微调计划，专门针对 `bottleneck` 调色板中的阻塞状态（红色），以将其改为暗红色，使视觉效果更舒适。

 摘要头
## [WIP] style: 微调瓶颈模拟器的阻塞状态颜色为暗红色

### 用户需求
将 `observatory.protoplasm.governance.bottleneck_sim` 中表示“阻塞”状态的亮红色（`rgb(255,50,50)`）改为暗红色，以降低视觉刺激。

### 评论
纯粹的风格调整。我们将使用 `rgb(180,40,40)` 作为新的暗红色，这既保留了警示性，又避免了过于刺眼。

### 目标
修改 `observatory/visualization/palette.py` 中的 `bottleneck` 方法，将阻塞状态的颜色值从亮红改为暗红。

### 基本原理
为了保持代码的语义一致性，我们只修改颜色值，不改变状态值（0.7）的映射逻辑。

### 标签
#intent/tune #flow/ready #priority/low #comp/cli #concept/ui #scope/ux #ai/instruct

---

### Script

#### Acts 1: 更新 `bottleneck` 调色板的阻塞颜色

将阻塞状态的颜色从 `rgb(255,50,50)` (亮红) 更新为 `rgb(180,40,40)` (暗红)。

~~~~~act
patch_file
observatory/visualization/palette.py
~~~~~
~~~~~python
        # Blocked (Red) ~ 0.7
        mask_blocked = (states >= 0.5) & (states < 0.9)
        colors[mask_blocked] = "rgb(255,50,50)"

        # Running (Bright White) ~ 1.0
~~~~~
~~~~~python
        # Blocked (Red) ~ 0.7
        mask_blocked = (states >= 0.5) & (states < 0.9)
        colors[mask_blocked] = "rgb(180,40,40)"

        # Running (Bright White) ~ 1.0
~~~~~

### 下一步建议
我们已经完成了颜色微调。你可以重新运行模拟器来验证新的颜色效果。如果没有进一步的颜色调整或 bug 报告，我们应该将前面两个计划（修复逻辑和本次颜色调整）合并为一个提交。
