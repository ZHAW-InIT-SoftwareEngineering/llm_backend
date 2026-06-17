import requests
from config.llm import SYSTEM_PROMPT, SGLANG_URL, MODEL, LLM_UNAVAILABLE_MESSAGE


def call_llm(user_message: str) -> str:
    try:
        response = requests.post(
            SGLANG_URL,
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.7,
                "max_tokens": 512,
            },
            timeout=60,
        )
        response.raise_for_status()

        data = response.json()
        llm_answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError, requests.RequestException):
        return LLM_UNAVAILABLE_MESSAGE

    return llm_answer
