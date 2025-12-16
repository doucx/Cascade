import pytest
from typer.testing import CliRunner
import cascade as cs
from cascade.context import get_current_context

# Skip if typer is not installed
pytest.importorskip("typer")

runner = CliRunner()

def test_cli_generator_from_context():
    """
    [V1.3 更新] 验证 CLI 生成器是从全局上下文读取 ParamSpec，
    而不是解析图结构。
    """
    # 1. 定义工作流构建函数
    # 这是一个新模式：为了让 CLI 扫描到参数，我们需要执行定义逻辑
    def workflow_def():
        # 清理上下文以确保测试隔离
        if hasattr(get_current_context(), "input_specs"):
            get_current_context().input_specs.clear()
        
        name = cs.Param("name", description="User name")
        count = cs.Param("count", default=1, type=int)
        
        @cs.task
        def greet(n, c):
            return f"Hello {n} " * c
            
        return greet(name, count)
    
    # 2. 模拟“导入时执行”：先运行一次定义，填充上下文
    target = workflow_def() 
    
    # Debug: Verify context is populated
    specs = get_current_context().get_all_specs()
    assert len(specs) == 2, f"Context should have 2 specs, got {len(specs)}"

    # 3. 生成 CLI
    # 注意：v1.3 cs.cli 可能既支持 LazyResult (为了兼容)，
    # 也支持直接利用 Context。这里我们传 target，验证它能否正确提取 Context 中的 Specs。
    app = cs.cli(target) 
    
    # 4. 验证 Help 信息 (证明 Spec 被正确读取)
    result = runner.invoke(app, ["--help"])
    if result.exit_code != 0:
        print(result.stdout)
    assert result.exit_code == 0
    assert "--name" in result.stdout
    assert "--count" in result.stdout
    assert "User name" in result.stdout

    # 5. 验证执行
    result = runner.invoke(app, ["--name", "World", "--count", "2"])
    assert result.exit_code == 0
    # Engine logs 默认可能在 stderr
    output = result.stdout + result.stderr
    assert "Hello World Hello World" in output