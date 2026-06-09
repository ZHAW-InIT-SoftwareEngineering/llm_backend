from fastapi import APIRouter

from api.schemas.chat.chat import ChatRequest, ChatResponse

from services.chat.chat import llm_call

router = APIRouter()

@router.post("/chat", response_model=ChatResponse, status_code=200)
def chat(chat_request: ChatRequest) -> ChatResponse:
    user_message = chat_request.user_message
    llm_answer = llm_call(user_message)

    return ChatResponse(
        llm_answer=llm_answer
    )
