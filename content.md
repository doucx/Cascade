I see the test failures. My previous refactoring of `BlueprintBuilder` was too aggressive and over-specialized it for the TCO "template" compilation, breaking its ability to compile normal, concrete workflows with nested dependencies. The tests correctly identified this regression.

The proper fix is to restore the compiler's general-purpose capability while still supporting the new template mode, controlled by a flag.

## [WIP] fix(compiler): Restore concrete graph compilation and add template mode

### 摘要头
`# [WIP] fix(compiler): Restore concrete graph compilation and add template mode`

### 用户需求
1.  修复 `BlueprintBuilder` 以支持两种编译模式：
    *   **Concrete Mode (default)**: Compiles a full `LazyResult` tree into an executable blueprint.
    *   **Template Mode**: Compiles a single root `LazyResult` into a reusable blueprint "template" where its arguments are promoted to blueprint inputs, for use by the VM's TCO loop.
2.  Update the `Engine` to explicitly request "Template Mode" when using the VM path.
3.  Update the tests to correctly test both modes.

### 错误分析
The `test_compile_data_dependency` and `test_compile_diamond_dependency` tests failed because `BlueprintBuilder.build` was modified to *only* perform template-style compilation. It treated the root task's arguments as blueprint inputs and did not recursively compile them if they were `LazyResult` objects. This is correct for a TCO agent template but incorrect for a standard, multi-step workflow.

The solution is to make the compilation mode explicit. The `build` method will default to concrete compilation (which handles nested dependencies) and will only enter template mode when a new `template=True` flag is passed.

### 评论
This fix makes the compiler more robust and its behavior more explicit. It resolves the regression while preserving the new functionality required for high-performance TCO.

### 目标
1.  Refactor `BlueprintBuilder` to support both compilation modes.
2.  Update `Engine._run_vm` to call the builder in template mode.
3.  Adjust compiler tests to reflect the new `build` signature.
4.  Ensure all tests pass.

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/parser #scope/core #ai/instruct #task/domain/runtime #task/object/compiler #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Refactor `BlueprintBuilder` to support dual modes

I will rename the template-specific logic and add the mode-switching logic to the public `build` method.

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/compiler.py
~~~~~
~~~~~python
    def build(self, target: Any) -> Blueprint:
        self.instructions.clear()
        self._visited.clear()
        self._register_counter = 0
        self._input_args_map = []
        self._input_kwargs_map = {}
        
        # Special handling for the root node to lift its arguments to input registers
        if isinstance(target, (LazyResult, MappedLazyResult)):
            self._compile_root(target)
        else:
            # Fallback for simple literals (though unlikely in practice)
            raise TypeError(f"Cannot compile non-LazyResult type: {type(target)}")
        
        return Blueprint(
            instructions=list(self.instructions),
            register_count=self._register_counter,
            input_args=list(self._input_args_map),
            input_kwargs=dict(self._input_kwargs_map)
        )

    def _allocate_register(self) -> Register:
        reg = Register(self._register_counter)
        self._register_counter += 1
        return reg

    def _compile_root(self, target: Union[LazyResult, MappedLazyResult]):
        """
        Compiles the root node. Arguments of the root node are treated as 
        Blueprint inputs.
        """
~~~~~
~~~~~python
    def build(self, target: Any, template: bool = False) -> Blueprint:
        self.instructions.clear()
        self._visited.clear()
        self._register_counter = 0
        self._input_args_map = []
        self._input_kwargs_map = {}
        
        if template:
            if not isinstance(target, (LazyResult, MappedLazyResult)):
                raise TypeError(f"Template compilation requires a LazyResult root, got {type(target)}")
            self._compile_template(target)
        else:
            self._visit(target)
        
        return Blueprint(
            instructions=list(self.instructions),
            register_count=self._register_counter,
            input_args=list(self._input_args_map),
            input_kwargs=dict(self._input_kwargs_map)
        )

    def _allocate_register(self) -> Register:
        reg = Register(self._register_counter)
        self._register_counter += 1
        return reg

    def _compile_template(self, target: Union[LazyResult, MappedLazyResult]):
        """
        Compiles the root node as a template. Arguments of the root node are 
        treated as Blueprint inputs and allocated input registers.
        """
~~~~~

#### Acts 2: Update the Engine to use template mode

The engine's VM path is the specific consumer of template blueprints.

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def _run_vm(self, target: Any) -> Any:
        """
        Executes the target using the AOT Blueprint/VM path.
        """
        # 1. Compile
        builder = BlueprintBuilder()
        blueprint = builder.build(target)

        # 2. Extract Initial Arguments
~~~~~
~~~~~python
    async def _run_vm(self, target: Any) -> Any:
        """
        Executes the target using the AOT Blueprint/VM path.
        """
        # 1. Compile in template mode
        builder = BlueprintBuilder()
        blueprint = builder.build(target, template=True)

        # 2. Extract Initial Arguments
~~~~~

#### Acts 3: Update compiler tests to use the new flag

The test that validates template compilation must now explicitly enable it. The other failing tests should now pass without changes.

~~~~~act
patch_file
tests/cascade-runtime/graph/test_compiler.py
~~~~~
~~~~~python
def test_compile_single_node_as_root():
    """
    Verify compiling a single task as root.
    Arguments should be promoted to Input Registers.
    """
    target = add_one(x=10) # 10 here acts as the 'default' or 'template' value structure

    builder = BlueprintBuilder()
    blueprint = builder.build(target)

    # Expected Registers:
~~~~~
~~~~~python
def test_compile_single_node_as_root():
    """
    Verify compiling a single task as root in template mode.
    Arguments should be promoted to Input Registers.
    """
    target = add_one(x=10) # 10 here acts as the 'default' or 'template' value structure

    builder = BlueprintBuilder()
    blueprint = builder.build(target, template=True)

    # Expected Registers:
~~~~~

### 下一步建议
The compiler logic is now correct and robust for both use cases. All tests should pass. We can now proceed with the final validation step: applying this new machinery to the `kuramoto` agent in the fireflies experiment.
