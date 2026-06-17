from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from api.schemas.chat.chat import ChatRequest, ChatResponse
from services.chat.chat import llm_call, llm_stream_call

router = APIRouter()

@router.post("/chat", response_model=ChatResponse, status_code=200)
def chat(chat_request: ChatRequest) -> ChatResponse:
    userMessage = chat_request.userMessage
    llm_answer = llm_call(userMessage)

    return ChatResponse(
        llm_answer=llm_answer
    )


@router.post("/chat/stream", status_code=200)
def chat_stream(chat_request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        llm_stream_call(chat_request.userMessage),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
