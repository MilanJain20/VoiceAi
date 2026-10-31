"""memory_config trims history and can keep an extractive summary."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.services.llm.memory import apply_memory, approximate_tokens


def test_window_keeps_the_system_prompt_and_the_tail() -> None:
    messages = [SystemMessage(content="stay")]
    for i in range(5):
        messages.append(HumanMessage(content=f"user {i}"))
        messages.append(AIMessage(content=f"agent {i}"))
    trimmed = apply_memory(
        messages, {"window_size": 2, "max_context_tokens": 8000, "summarize": False}
    )
    assert trimmed[0].content == "stay"
    assert len(trimmed) == 3
    assert trimmed[-1].content == "agent 4"


def test_summarize_keeps_a_note_about_dropped_turns() -> None:
    messages = [SystemMessage(content="stay"), HumanMessage(content="remember the password drawer")]
    messages += [AIMessage(content="noted"), HumanMessage(content="latest")]
    trimmed = apply_memory(
        messages, {"window_size": 1, "max_context_tokens": 8000, "summarize": True}
    )
    assert any("Summary of earlier turns" in getattr(item, "content", "") for item in trimmed)
    assert trimmed[-1].content == "latest"


def test_token_budget_drops_older_turns() -> None:
    fat = "word " * 400
    messages = [
        SystemMessage(content="sys"),
        HumanMessage(content=fat),
        AIMessage(content="short"),
    ]
    budget = approximate_tokens("sys") + approximate_tokens("short") + 10
    trimmed = apply_memory(
        messages, {"window_size": 20, "max_context_tokens": budget, "summarize": False}
    )
    assert all(getattr(item, "content", "") != fat for item in trimmed)
    assert trimmed[-1].content == "short"
