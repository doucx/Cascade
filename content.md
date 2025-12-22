You've caught the exact flaw. My apologies, the migration script was incomplete. It successfully renamed the packages and updated their internal dependencies, but it crucially missed updating the *workspace definition* in the root `pyproject.toml`.

The error message from `uv` is perfect feedback: the workspace manager (`uv`) knows about a package named `cascade-spec` because it found the directory, but it can't find its configuration in the `[tool.uv.sources]` table because the key is still the old name, `cascade-interfaces`.

I will now generate a plan to patch the root `pyproject.toml` to fix this inconsistency.

## [WIP] fix: Synchronize root pyproject.toml with refactored workspace

### 错误分析
The installation failed because the migration script did not update the workspace configuration keys (`cascade-interfaces`, `cascade-runtime`, etc.) in the root `pyproject.toml`'s `[tool.uv.sources]` and `[tool.hatch.workspaces]` sections. This created a mismatch between the physical package names on disk (`cascade-spec`) and the names defined in the workspace configuration, causing `uv` to fail.

### 用户需求
Correct the root `pyproject.toml` so that the workspace tooling can recognize the newly renamed packages, allowing the `uv pip install -e .[dev]` command to succeed.

### 评论
This is a critical final step for the structural refactoring. The root `pyproject.toml` acts as the central index for the entire monorepo. Aligning it with the new package structure will resolve the installation error and properly reintegrate the refactored packages into the development environment.

### 目标
1.  Patch the `pyproject.toml` file in the project root.
2.  Update the keys in the `[tool.uv.sources]` table to match the new package names (`cascade-spec`, `cascade-engine`, `cascade-sdk`).
3.  Update the paths in the `[tool.hatch.workspaces]` list to reflect the renamed package directories.

### 基本原理
The previous script completed the most difficult part of the refactoring (moving files and directories). Now, a simple, targeted `patch_file` operation is the safest and most direct way to fix the configuration inconsistency in the root `pyproject.toml`.

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/workspace-config #task/action/refactor #task/state/continue #task/status/active

---

### Script

#### Acts 1: Correct the workspace configuration in the root pyproject.toml
We will apply two precise patches to the root `pyproject.toml` to update both the `uv` and `hatch` workspace definitions.

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~
[tool.uv.sources]
cascade-interfaces = { workspace = true }
cascade-runtime = { workspace = true }
cascade-py = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
~~~~~
~~~~~
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~
[tool.hatch.workspaces]
packages = [
    "packages/cascade-interfaces",
    "packages/cascade-runtime",
    "packages/cascade-py",
    "packages/cascade-provider-ipfs",
]
~~~~~
~~~~~
[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-engine",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
]
~~~~~

