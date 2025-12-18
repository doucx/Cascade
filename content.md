You've found another excellent and subtle bug. My apologies. The `pytest` error trace is the smoking gun, and your analysis is spot on.

This is a classic Python packaging mistake on my part, especially during a refactor.

## [WIP] fix(build): Add missing __init__.py to new packages for proper discovery

### 錯誤分析
`pytest` fails during test collection with an `ImportError: cannot import name 'MessageStore' from 'cascade.common.messaging'`. The key part of the error is `(unknown location)`, which is a strong indicator of a namespace package problem.

The root cause is that I created the directory `packages/cascade-common/src/cascade/common/messaging` and placed `bus.py` and `protocols.py` inside it, but I **failed to create an `__init__.py` file within that directory**.

Without `__init__.py`, Python 3 treats `cascade.common.messaging` as an implicit "namespace package". When `cascade.runtime.renderers` tries to `from cascade.common.messaging import MessageStore`, the importer finds the `messaging` namespace but doesn't know to look *inside* the `bus.py` file to find the `MessageStore` class. This results in the `ImportError`.

### 用户需求
修复项目结构，添加所有必需的 `__init__.py` 文件，以确保 Python's import system can correctly discover and load modules and their contents from the new `cascade-common` package, allowing `pytest` to run without import errors.

### 评论
This is a critical fix that corrects a fundamental Python packaging error. Properly defining packages with `__init__.py` files is essential for creating a reliable and predictable import structure. This fix will unblock the test suite and allow us to proceed with development on a stable foundation. It also highlights the value of running tests immediately after a refactor to catch such integration issues.

### 目标
1.  Create the missing `__init__.py` file in `packages/cascade-common/src/cascade/common/messaging`.
2.  Populate this new `__init__.py` to expose the public API of the messaging module (like the global `bus` singleton), making it easier to import.
3.  Add any other missing `__init__.py` files in the new package structures to ensure the entire `cascade` namespace is correctly constructed.

### 基本原理
We will use `write_file` to create the necessary `__init__.py` files. The most important one, in `.../messaging/`, will not be empty; it will contain imports from its sibling modules (`bus.py`, `protocols.py`) to define the public API for the `cascade.common.messaging` package. This is a standard Python practice that makes packages easier to use and fixes the import resolution error.

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/dx #ai/instruct #task/domain/tooling #task/object/packaging #task/action/fix #task/state/continue

---

### Script

#### Acts 1: Create `__init__.py` files for the `cascade.common` namespace

First, we need to ensure that `cascade` and `cascade.common` are themselves recognized as packages.

~~~~~act
write_file
packages/cascade-common/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-interfaces) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-common/src/cascade/common/__init__.py
~~~~~
~~~~~python
# This space intentionally left blank.
~~~~~

#### Acts 2: Create the critical `__init__.py` for the messaging package

This is the core of the fix. We'll create the file and define the public API for easier imports.

~~~~~act
write_file
packages/cascade-common/src/cascade/common/messaging/__init__.py
~~~~~
~~~~~python
from .bus import bus, MessageBus, MessageStore
from . import protocols

__all__ = ["bus", "MessageBus", "MessageStore", "protocols"]
~~~~~

#### Acts 3: Ensure `__init__.py` files exist for CLI packages

To prevent future issues, let's ensure the intermediate `cascade.cli` namespace is also a proper package.

~~~~~act
write_file
packages/cascade-cli-observer/src/cascade/cli/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-interfaces) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-cli-controller/src/cascade/cli/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-interfaces) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

### 下一步建议
The missing `__init__.py` files have been created, and the `messaging` package now has a proper public API. The import errors should now be resolved.

Please run `pytest` again.

Once the tests pass (or at least start running without import errors), we can finally proceed with implementing the core logic for the `cs-observer watch` command.
