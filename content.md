Of course. Dealing with linting errors is crucial for maintaining code quality and preventing potential bugs. I'll fix the 14 issues reported by Ruff.

Here is the plan to address each error.

## [WIP] fix: Resolve 14 ruff linting errors across the codebase

### 用户需求

The user has provided the output of `ruff check .`, which lists 14 distinct linting errors, including unused variables (`F841`), misplaced imports (`E402`), and undefined names (`F821`). The goal is to fix all of these reported issues.

### 评论

This is a standard code hygiene task. The fixes are straightforward and will improve the overall quality and readability of the codebase without altering any logic. Applying these changes systematically will ensure the codebase is clean and compliant with the linter's rules.

### 目标

1.  Remove all unused local variables (`F841`).
2.  Move all module-level imports to the top of their respective files (`E402`).
3.  Add missing imports to resolve undefined name errors (`F821`).
4.  Ensure the codebase passes a `ruff check .` without any errors after the changes.

### 基本原理

I will address each file and error combination reported by Ruff using the `patch_file` command.

-   For unused variables, I will remove the assignment part of the statement (e.g., `variable = ...` becomes `...`) or the entire line if it has no side effects.
-   For misplaced imports, I will move the import statement to the top of the file, grouping it with other similar imports.
-   For undefined names, I will add the necessary import statement at the top of the file.

This approach ensures each fix is atomic and directly corresponds to a reported problem.

### 标签

#intent/fix #flow/ready #priority/medium #comp/tests #comp/cli #comp/engine #scope/dx #ai/instruct #task/domain/testing #task/object/linting #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: Fix Unused Variables (F841)

First, I'll address all the unused variable errors.

Removing `consumer_queues` from `proto_direct_connect.py`.
~~~~~act
patch_file
observatory/protoplasm/networking/proto_direct_connect.py
~~~~~
~~~~~python
    # Setup Consumers
    # Each consumer is a queue attached to a subscription
    consumer_queues = []

    # We use a latch (Event) to signal completion
    completion_event = asyncio.Event()
~~~~~
~~~~~python
    # Setup Consumers
    # Each consumer is a queue attached to a subscription

    # We use a latch (Event) to signal completion
    completion_event = asyncio.Event()
~~~~~

Removing assignment to `results` in `recursion_test.py`.
~~~~~act
patch_file
observatory/protoplasm/physics/recursion_test.py
~~~~~
~~~~~python
    try:
        # Wait for all agents to finish
        results = await asyncio.gather(*tasks)
        print(
            f"\n✅ Successfully reached {NUM_GENERATIONS} generations for all {NUM_AGENTS} agents."
        )
~~~~~
~~~~~python
    try:
        # Wait for all agents to finish
        await asyncio.gather(*tasks)
        print(
            f"\n✅ Successfully reached {NUM_GENERATIONS} generations for all {NUM_AGENTS} agents."
        )
~~~~~

Removing unused `rate` variable in `debug_headless_throughput.py`.
~~~~~act
patch_file
observatory/scripts/debug_headless_throughput.py
~~~~~
~~~~~python
            now = time.time()
            interval = now - last_report_time
            rate = (flash_count - (flash_times[0] if flash_times else 0)) / interval

            # Simple reporting
            current_rate = (
~~~~~
~~~~~python
            now = time.time()
            interval = now - last_report_time

            # Simple reporting
            current_rate = (
~~~~~

Removing assignment to `updates_count` in `raw_app.py`.
~~~~~act
patch_file
observatory/visualization/raw_app.py
~~~~~
~~~~~python
            # 1. Process Updates
            flush_start = time.perf_counter()
            updates_count = await self._flush_buffer()
            flush_ms = (time.perf_counter() - flush_start) * 1000
~~~~~
~~~~~python
            # 1. Process Updates
            flush_start = time.perf_counter()
            await self._flush_buffer()
            flush_ms = (time.perf_counter() - flush_start) * 1000
~~~~~

Removing unused `node_map` in `strategies.py`.
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
    ):
        # ... logic moved from Engine ...
        node_map = {node.id: node for node in graph.nodes}
        if graph.nodes:
            target_node = graph.nodes[-1]
~~~~~
~~~~~python
    ):
        # ... logic moved from Engine ...
        if graph.nodes:
            target_node = graph.nodes[-1]
~~~~~

Removing unused `result` variable in `test_e2e_cli_local_backend.py`.
~~~~~act
patch_file
tests/cli/e2e/test_e2e_cli_local_backend.py
~~~~~
~~~~~python
    )

    runner = CliRunner()
    result = runner.invoke(
        controller_app,
        ["set-limit", "--scope", "global", "--rate", "1/s", "--backend", "mqtt"],
    )

    # Even though the command "fails" without a mock, it shouldn't touch the filesystem.
~~~~~
~~~~~python
    )

    runner = CliRunner()
    runner.invoke(
        controller_app,
        ["set-limit", "--scope", "global", "--rate", "1/s", "--backend", "mqtt"],
    )

    # Even though the command "fails" without a mock, it shouldn't touch the filesystem.
~~~~~

Removing unused `idx_run1` in `test_engine_recursion.py`. The call to `index()` remains to assert the task ran.
~~~~~act
patch_file
tests/engine/runtime/test_engine_recursion.py
~~~~~
~~~~~python
    try:
        idx_run1 = calls.index(call.step_one_run())
        idx_run2 = calls.index(call.step_two_run())
    except ValueError:
~~~~~
~~~~~python
    try:
        calls.index(call.step_one_run())
        idx_run2 = calls.index(call.step_two_run())
    except ValueError:
~~~~~

#### Acts 2: Fix Misplaced Imports (E402)

Now, I'll move the misplaced imports to the top of their files.

Moving `Rule` import in `rendering.py`.
~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/rendering.py
~~~~~
~~~~~python
from rich.console import Console
from rich.theme import Theme

from cascade.common.messaging import protocols, MessageStore
~~~~~
~~~~~python
from rich.console import Console
from rich.rule import Rule
from rich.theme import Theme

from cascade.common.messaging import protocols, MessageStore
~~~~~
~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/rendering.py
~~~~~
~~~~~python
    }
)


from rich.rule import Rule


class RichCliRenderer(protocols.Renderer):
~~~~~
~~~~~python
    }
)


class RichCliRenderer(protocols.Renderer):
~~~~~

Moving typing imports in `template.py`.
~~~~~act
patch_file
packages/cascade-library/src/cascade/providers/template.py
~~~~~
~~~~~python
from cascade.spec.task import task
from cascade.providers import LazyFactory

try:
~~~~~
~~~~~python
from typing import Any, Dict, Optional

from cascade.spec.task import task
from cascade.providers import LazyFactory

try:
~~~~~
~~~~~act
patch_file
packages/cascade-library/src/cascade/providers/template.py
~~~~~
~~~~~python
        return render_template


from typing import Dict, Any, Optional


@task(name="template")
def render_template(
~~~~~
~~~~~python
        return render_template


@task(name="template")
def render_template(
~~~~~

Moving messaging and renderer imports in `cascade/__init__.py`.
~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
# --- Main Run Entrypoint ---
from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer, JsonRenderer


def _create_state_backend_factory(
~~~~~
~~~~~python
from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer, JsonRenderer

# --- Main Run Entrypoint ---


def _create_state_backend_factory(
~~~~~

#### Acts 3: Fix Undefined Names (F821)

Finally, I'll add the missing imports for `LazyResult` and `MappedLazyResult`.

Adding imports to `engine.py`.
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.spec.resource import ResourceDefinition
from cascade.spec.constraint import GlobalConstraint
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
~~~~~
~~~~~python
from cascade.spec.resource import ResourceDefinition
from cascade.spec.constraint import GlobalConstraint
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
~~~~~

### 下一步建议

The linting errors should now be resolved. I recommend running `ruff check .` again to confirm that all issues have been fixed. If the check passes, we can proceed to create a `[COMMIT]` plan to save these changes to version control.
