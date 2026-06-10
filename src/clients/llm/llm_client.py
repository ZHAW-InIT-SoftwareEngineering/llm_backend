import requests


SGLANG_URL = "http://host.docker.internal:30000/v1/chat/completions"
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
LLM_UNAVAILABLE_MESSAGE = "GPU is stopped to protect our cluster. Please try again later."


def call_llm(user_message: str) -> str:
    try:
        response = requests.post(
            SGLANG_URL,
            json={
                "model": MODEL,
                "messages": [
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
