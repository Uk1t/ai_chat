from fastapi import APIRouter
from schemas import Question, Answer
from services.bot_service import ask_assistant, chat_histories

router = APIRouter(prefix="/ai", tags=["AI bot"])

@router.post("/ask", response_model=Answer)
def ask_bot(question: Question):
    answer_text = ask_assistant(user_id=question.user_id, question=question.description)
    return {"answer": answer_text}

# Новый маршрут: получить историю чата
@router.get("/history")
def get_history(user_id: str):
    """
    Возвращает историю чата для конкретного пользователя
    """
    history = chat_histories.get(user_id, [])
    # приводим к JSON-формату
    return {
        "history": [
            {"role": "user" if isinstance(m, Question) or getattr(m, 'role', '')=='user' else 'bot',
             "content": m.content}
            if hasattr(m, 'content') else {"role":"unknown","content":str(m)}
            for m in history
        ]
    }

# Новый маршрут: очистить историю чата
@router.post("/clear")
def clear_history(user_id: str):
    chat_histories[user_id] = []
    return {"status": "ok"}