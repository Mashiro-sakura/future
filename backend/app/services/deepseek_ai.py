"""
DeepSeek AI 服务 - 封装为 FastAPI 可调用的服务
"""
from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """获取或初始化 OpenAI 客户端（单例）"""
    global _client
    if _client is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置，请在 .env 文件中添加")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
    return _client


def chat(
    prompt: str,
    system_prompt: str = "你是一个专业的期货分析师助手",
    model: str = "deepseek-chat",
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """
    调用 DeepSeek 聊天接口

    Args:
        prompt: 用户输入
        system_prompt: 系统提示词
        model: 模型名 (deepseek-chat / deepseek-reasoner)
        temperature: 温度 (0-2)
        max_tokens: 最大输出 token 数

    Returns:
        模型回复文本
    """
    response = _get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content


def analyze_futures_report(
    report_text: str,
    model: str = "deepseek-chat",
) -> str:
    """
    专用方法：分析期货报告内容

    Args:
        report_text: 期货分析报告文本

    Returns:
        AI 分析建议
    """
    system_prompt = """你是一个专业的期货分析师。请基于提供的期现分析报告数据，
给出简洁的投资建议，包括：
1. 当前基差状态
2. 主要风险提示
3. 操作建议（多/空/观望）

回复控制在200字以内。"""
    return chat(
        prompt=f"以下是今日期现分析报告：\n\n{report_text}\n\n请给出分析和建议：",
        system_prompt=system_prompt,
        model=model,
        temperature=0.5,
        max_tokens=500
    )
