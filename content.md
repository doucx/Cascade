#### Acts 4: 提交变更

现在，所有测试都已修复，我们将把这些修复作为一个原子提交。

~~~~~act
git_add
packages/cascade-compiler/tests/integration/test_assembly_purity.py
packages/cascade-compiler/tests/integration/test_graph_purity.py
packages/cascade-compiler/tests/integration/test_manifest_content.py
packages/cascade-compiler/tests/integration/test_sovereign_wiring.py
packages/cascade-compiler/tests/unit/frontend/test_generator.py
packages/cascade-vm/tests/integration/test_linker_validation.py
packages/cascade-vm/tests/integration/test_ref_architecture.py
packages/cascade-vm/tests/integration/test_resource_contention.py
packages/cascade-vm/tests/integration/test_resource_sentry.py
packages/cascade-vm/tests/integration/test_source_node_execution.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(tests): adapt tests to IRGenerator returning GenerationResult

The `IRGenerator.generate` method was updated to return a `GenerationResult` object containing both the `ir` and an `executables` registry, instead of just the raw `GraphIR`.

This change broke all consuming tests, which were still expecting `GraphIR` and attempting to access attributes like `.nodes` directly, leading to `AttributeError`.

This commit updates all affected test cases to correctly unpack the `GenerationResult` object, extracting the `.ir` attribute before passing it to the compiler backend or performing assertions. This brings the test suite back to a green state and aligns it with the new, more explicit compiler frontend API.
~~~~~

