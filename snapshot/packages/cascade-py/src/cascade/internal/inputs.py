import os
from typing import Any, Dict, Optional
from cascade.spec.task import task

# 这个任务的职责是从 Engine 提供的参数上下文中获取值。
# 'params_context' 将由 Engine 的参数解析器在运行时注入。
@task(name="_get_param_value")
def _get_param_value(name: str, params_context: Dict[str, Any]) -> Any:
    # 注意：Engine 负责确保 params_context 存在。
    # 如果参数缺失且无默认值，应该在解析阶段或这里报错。
    # 但由于默认值逻辑在 InputSpec 中，这里只负责简单的提取。
    # 实际的默认值回退逻辑可能需要在 Engine/ArgumentResolver 中处理，
    # 或者这个任务本身需要知道 default 值。
    # 简化起见，假设 Engine/Resolver 已经处理了 default 值的注入，
    # 或者 params_context 中包含了所有有效的值。
    
    # 根据 v1.3 设计，InputSpec 持有 default。
    # 如果 ArgumentResolver 没有处理 default，这里就会失败。
    # 为了健壮性，这里的 params_context 应该包含最终决定的值。
    return params_context[name]

# 这个任务的职责是从 OS 环境中获取值。
@task(name="_get_env_var")
def _get_env_var(name: str) -> Optional[str]:
    return os.getenv(name)