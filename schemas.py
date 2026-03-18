from pydantic import BaseModel

class Question(BaseModel):
    user_id: str         # уникальный ID пользователя
    description: str     # текст вопроса

class Answer(BaseModel):
    answer: str