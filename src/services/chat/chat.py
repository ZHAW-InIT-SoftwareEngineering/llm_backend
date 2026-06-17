from collections.abc import Iterator

from clients.llm.llm_client import call_llm, stream_call_llm


def llm_call(userMessage: str) -> str:
    return call_llm(userMessage)


def llm_stream_call(userMessage: str) -> Iterator[str]:
    return stream_call_llm(userMessage)
