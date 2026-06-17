from pydantic import BaseModel

class ChatRequest(BaseModel): 
    userMessage: str


class ChatResponse(BaseModel):
    llm_answer: str
