It appears my previous attempt didn't fully resolve the issues, and `ruff format` may have revealed a slightly incorrect patch for the import locations. My apologies. Let's fix the remaining three errors.

## [WIP] fix: Resolve remaining 3 ruff linting errors

### 用户需求

The user has provided the output of a combined `ruff format . | ruff check .` command, which shows 3 remaining linting errors: one unused variable (`F841`) and two misplaced imports (`E402`). The goal is to correct these final issues.

### 评论

It's good that `ruff format` was run, as it helps isolate the true logical errors from simple formatting ones. The remaining issues are straightforward: an unused `deque` and misplaced imports that need to be moved to the top-level import block of the module. This plan will address them precisely.

### 目标

1.  Remove the unused `flash_times` variable from `debug_headless_throughput.py`.
2.  Relocate the `bus` and `renderer` imports in `packages/cascade-sdk/src/cascade/__init__.py` to the top of the file to comply with the `E402` rule.
3.  Achieve a clean `ruff check .` pass.

### 基本原理

I will apply two sets of patches:
1.  A simple line removal in `debug_headless_throughput.py` to fix the `F841` error. The variable was left over from a previous calculation that has since been removed.
2.  A two-part `patch_file` operation on `packages/cascade-sdk/src/cascade/__init__.py` to move the import statements from the middle of the file to the main import block at the top, resolving the `E402` errors.

### 标签

#intent/fix #flow/ready #priority/medium #comp/cli #scope/dx #ai/instruct #task/domain/testing #task/object/linting #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Fix Unused Variable in Throughput Script

The `flash_times` variable is no longer used for rate calculation. I will remove its initialization.

~~~~~act
patch_file
observatory/scripts/debug_headless_throughput.py
~~~~~
~~~~~python
    # --- Flash Counter ---
    flash_count = 0
    flash_times = deque()

    class HeadlessConnector:
~~~~~
~~~~~python
    # --- Flash Counter ---
    flash_count = 0

    class HeadlessConnector:
~~~~~

#### Acts 2: Correct Import Order in Cascade SDK

I will move the misplaced imports to the top of the `__init__.py` file to resolve the `E402` errors. First, I'll add them to the main import block.

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
from .tools.cli import create_cli
from cascade.graph.serialize import to_json, from_json


# --- V1.3 Factory Functions ---
~~~~~
~~~~~python
from .tools.cli import create_cli
from cascade.graph.serialize import to_json, from_json

# Common utilities for the run entrypoint
from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer, JsonRenderer


# --- V1.3 Factory Functions ---
~~~~~

Next, I'll remove them from their incorrect location further down in the file.

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
    except AttributeError:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer, JsonRenderer

# --- Main Run Entrypoint ---
~~~~~
~~~~~python
    except AttributeError:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# --- Main Run Entrypoint ---
~~~~~

### 下一步建议

All reported errors have been addressed. Please run `ruff check .` again to verify the fix. If it passes, I will generate the final `[COMMIT]` plan to save all the linting fixes.
