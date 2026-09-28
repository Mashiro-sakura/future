"""
DeepSeek API 连通性测试
在 PyCharm 中直接运行此文件即可测试
"""
from openai import OpenAI

# ===== 在这里填入你的 API Key =====
DEEPSEEK_API_KEY = "sk-your-key-here"  # ← 替换成你的 key

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

print("=" * 50)
print("🔍 正在测试 DeepSeek API 连接...")
print("=" * 50)

try:
    response = client.chat.completions.create(
        model="deepseek-chat",  # 或 "deepseek-reasoner"（R1 推理模型）
        messages=[
            {"role": "system", "content": "你是一个专业的期货分析师助手"},
            {"role": "user", "content": "用一句话介绍期现分析（基差分析）的核心逻辑"}
        ],
        temperature=0.7,
        max_tokens=200
    )

    print("\n✅ 连接成功！")
    print("-" * 50)
    print(f"模型: {response.model}")
    print(f"Token 用量: {response.usage.total_tokens} (输入 {response.usage.prompt_tokens}, 输出 {response.usage.completion_tokens})")
    print("-" * 50)
    print(f"回复:\n{response.choices[0].message.content}")
    print("=" * 50)

except Exception as e:
    print(f"\n❌ 连接失败: {e}")
    print("\n可能的原因:")
    print("  1. API Key 错误")
    print("  2. 网络问题（需要代理？）")
    print("  3. DeepSeek 服务暂时不可用")
