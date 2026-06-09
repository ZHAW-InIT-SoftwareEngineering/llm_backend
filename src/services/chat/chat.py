from clients.llm.llm_client import call_llm


def llm_call(user_message: str) -> str:
    return call_llm(user_message)
