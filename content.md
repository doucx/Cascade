## [WIP] debug(vm): 使用关键字参数调用 final_task 以隔离问题

### 用户需求
修改 `test_e2e_vm_run.py`，将对 `final_task` 的调用从位置参数改为关键字参数，以验证问题是否出在 `IRGenerator` 的位置参数到命名参数的映射逻辑中。

### 评论
这是一个经典的调试技术。通过切换到另一种代码路径（关键字参数），我们可以隔离或确认 Bug 的位置。如果测试通过，就证明 `IRGenerator` 中处理 `*args` 的逻辑存在缺陷；如果测试仍然失败，问题就出在更深层次的、与参数传递无关的地方。

### 目标
修改 `final_result_lr = final_task(main_result, setup_result)` 为 `final_result_lr = final_task(res=main_result, setup_status=setup_result)`。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #task/domain/testing #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修改 E2E 测试中的函数调用

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_e2e_vm_run.py
~~~~~
~~~~~python.old
    main_result = main_task(10).with_constraints(gpu=1).run_if(condition_result).after(setup_result)
    
    final_result_lr = final_task(main_result, setup_result)

    # 2. Manually compile the workflow
~~~~~
~~~~~python.new
    main_result = main_task(10).with_constraints(gpu=1).run_if(condition_result).after(setup_result)
    
    final_result_lr = final_task(res=main_result, setup_status=setup_result)

    # 2. Manually compile the workflow
~~~~~

### 下一步建议
请运行测试。这将是我们定位此问题的决定性一步。
