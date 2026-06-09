from pydantic import BaseModel

class ChatRequest(BaseModel): 
    user_message: str


class ChatResponse(BaseModel):
    llm_answer: str