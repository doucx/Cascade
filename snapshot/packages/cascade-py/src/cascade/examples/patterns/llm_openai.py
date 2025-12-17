import cascade as cs
from cascade.providers.http import HttpResponse

# 1. 定义子流程的输入参数
api_key = cs.Env("OPENAI_API_KEY", description="OpenAI API Key")
model = cs.Param("model", default="gpt-4-turbo")
prompt_template = cs.Param("prompt_template")
# context 将是一个字典，其值可以是 LazyResult 或字面量
context = cs.Param("context", default={})

# 2. 组合原子任务 (这就是模式的核心)
# 步骤 A: 渲染 Prompt
final_prompt = cs.template(template_string=prompt_template, context=context)

# 步骤 B: 调用 HTTP API (使用第一阶段构建的积木)
api_response = cs.http.post(
    url="https://api.openai.com/v1/chat/completions",
    headers={
        "Content-Type": "application/json",
        # 使用 cs.template 动态构建认证头
        "Authorization": cs.template("Bearer {{ key }}", key=api_key)
    },
    json={
        "model": model,
        "messages": [{"role": "user", "content": final_prompt}]
    }
).with_retry(max_attempts=3, delay=5) # 精确地对网络调用进行重试

# 步骤 C: 解析响应 (一个简单的纯函数任务)
@cs.task
def parse_response(response: "HttpResponse"):
    if response.status >= 400:
        raise RuntimeError(f"API Error: {response.status} - {response.text()}")
    return response.json()["choices"][0]["message"]["content"]

parsed_text = parse_response(api_response)

# 3. 暴露最终结果作为子流程的 'target'
result = parsed_text