import json
from typing import Any, Iterable, Mapping


def build_chat_context_parts(
    audit_contexts: Mapping[str, Any],
    benchmark_contexts: Mapping[str, Any],
    data_contexts: Iterable[str] | None = None,
) -> list[str]:
    context_parts = []
    if audit_contexts:
        context_parts.append("### AUDIT DATA ###")
        for filename, data in audit_contexts.items():
            context_parts.append(f"File: {filename}\n{json.dumps(data, indent=2)}")

    if benchmark_contexts:
        context_parts.append("### BENCHMARK DATA ###")
        for title, data in benchmark_contexts.items():
            context_parts.append(f"Benchmark: {title}\n{json.dumps(data, indent=2)}")

    for data_context in data_contexts or []:
        if data_context:
            context_parts.append(data_context)

    return context_parts


def build_chat_prompt(user_prompt: str, context_parts: Iterable[str]) -> str:
    parts = list(context_parts)
    if not parts:
        return user_prompt
    return f"CONTEXT INFORMATION:\n\n" + "\n\n".join(parts) + f"\n\nUSER QUESTION: {user_prompt}"
