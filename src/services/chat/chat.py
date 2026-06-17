from clients.llm.llm_client import call_llm


def llm_call(userMessage: str) -> str:
    return call_llm(userMessage)
