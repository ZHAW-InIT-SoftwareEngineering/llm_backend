import requests
from config.llm import SYSTEM_PROMPT, SGLANG_URL, MODEL, LLM_UNAVAILABLE_MESSAGE
import json
from collections.abc import Iterator


def call_llm(userMessage: str) -> str:
    return userMessage
    '''
    try:
        response = requests.post(
            SGLANG_URL,
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": userMessage},
                ],
                "temperature": 0.5,
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
    '''


def stream_call_llm(userMessage: str) -> Iterator[str]:
    try:
        with requests.post(
            SGLANG_URL,
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": userMessage},
                ],
                "temperature": 0.5,
                "max_tokens": 512,
                "stream": True,
            },
            stream=True,
            timeout=(10, 60),
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                if not line.startswith("data:"):
                    continue

                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break

                try:
                    payload = json.loads(data)
                    delta = payload["choices"][0].get("delta", {}).get("content")
                except (KeyError, IndexError, TypeError, ValueError):
                    continue

                if delta:
                    yield f"data: {json.dumps({'delta': delta})}\n\n"
    except requests.RequestException:
        yield f"data: {json.dumps({'delta': LLM_UNAVAILABLE_MESSAGE})}\n\n"

    yield "data: [DONE]\n\n"
