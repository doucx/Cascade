Thank you for providing the detailed file tree. This is incredibly helpful and reveals the exact problem. My apologies; my migration script was flawed in a very specific way.

### 错误分析
The file listing shows this structure:
```
packages
└── cascade-sdk
    └── cascade-py
        ├── pyproject.toml
        └── src
```
This confirms that the script did not *rename* `packages/cascade-py` to `packages/cascade-sdk`. Instead, it created a new directory `packages/cascade-sdk` and then *moved* the `cascade-py` directory **inside** it.

This is a classic filesystem mistake. The consequence is that `uv` correctly finds the `cascade-sdk` directory but, as the error states, there is no `pyproject.toml` directly within it. The actual package is one level too deep.

The fix is to correct this improper nesting.

## [WIP] fix: Correct malformed package structure from failed migration

### 错误分析
The previous migration script incorrectly moved the `cascade-py` directory *inside* `cascade-sdk` instead of renaming it. This resulted in the path `packages/cascade-sdk/cascade-py`, breaking the workspace structure and causing the `uv` installation to fail because `pyproject.toml` was not at the expected location.

### 用户需求
The workspace is in a broken, nested state. The file structure needs to be corrected so that `packages/cascade-sdk` is a valid package and the project can be installed.

### 评论
This plan executes a surgical fix for the filesystem error. By using a three-step move-delete-rename process, we can safely un-nest the `cascade-py` contents and restore the `cascade-sdk` package to its correct structure without any data loss. This will finally bring the repository into a consistent state that matches the workspace configuration.

### 目标
1.  Move the nested `packages/cascade-sdk/cascade-py` directory to a temporary location at the top level of `packages`.
2.  Delete the now-empty and problematic `packages/cascade-sdk` directory.
3.  Rename the temporary directory to the correct final name, `packages/cascade-sdk`.

### 基本原理
Directly moving the contents out of the nested directory is complex. A safer, more atomic approach is to move the entire valuable subdirectory (`cascade-py`) out to a temporary safe harbor (`cascade-py-temp`), remove the malformed container (`cascade-sdk`), and then rename the safe harbor to its final, correct name. This ensures the integrity of the package contents throughout the operation.

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/package-structure #task/action/refactor #task/state/continue #task/status/active

---

### Script

#### Acts 1: Correct the nested package structure
We will now execute the three-step fix.

First, move the valuable nested directory to a safe temporary location.
~~~~~act
move_file
packages/cascade-sdk/cascade-py
packages/cascade-py-temp
~~~~~

Second, remove the now-empty, malformed `cascade-sdk` directory.
~~~~~act
run_command
~~~~~
~~~~~
rm -rf packages/cascade-sdk
~~~~~

Finally, rename the temporary directory to its correct final name.
~~~~~act
move_file
packages/cascade-py-temp
packages/cascade-sdk
~~~~~
