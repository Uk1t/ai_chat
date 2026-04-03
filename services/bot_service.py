import os
from typing import Dict, List
from dotenv import load_dotenv
import openai
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

# =====================================================
# 🧠 SYSTEM PROMPT
# =====================================================
SYSTEM_PROMPT = """
Ты — менеджер по продажам трубопроводной арматуры компании Newkey.
ВАЖНО:"Ты работаешь ТОЛЬКО с переданными данными с сайта newkey.ru!
Любая информация вне этих данных запрещена."


ВАЖНО:
Если пользователь указывает артикул (например NK-BML8/6),
обязательно выполни поиск и найди точную страницу товара на сайте www.newkey.ru.
Возвращай форматированный текст в формате HTML!


Строго:
- Не придумывать товары, цены, наличие, артикулы.
- Не делать предположения или объединять источники.
- Указывать цену и наличие только если явно есть.
- Если нет данных — не указывать эти характеристики.
- Если нет цены, то указывать "цена по согласованию с менеджером"
- Кратко, как менеджер.
- Формат ответа:

Название товара: ...
Характеристики: ...
Цена: ...

Если несколько товаров — вывести не более 5 и написать "Есть больше вариантов, уточните параметры".
"""

# =====================================================
# 🤖 Yandex GPT
# =====================================================
YANDEX_API_KEY = os.getenv("YANDEX_CLOUD_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_CLOUD_FOLDER_ID")
YANDEX_MODEL = "qwen3.5-35b-a3b-fp8"

if not YANDEX_API_KEY:
    raise ValueError("YANDEX_CLOUD_API_KEY не найден")
if not YANDEX_FOLDER_ID:
    raise ValueError("YANDEX_CLOUD_FOLDER_ID не найден")

client = openai.OpenAI(
    api_key=YANDEX_API_KEY,
    base_url="https://ai.api.cloud.yandex.net/v1"
)



# =====================================================
# 🧠 GENERATE ANSWER
# =====================================================
def generate_answer(question: str, history: List) -> str:
    history_text = ""
    for msg in history[-6:]:
        if isinstance(msg, HumanMessage):
            history_text += f"Пользователь: {msg.content}\n"
        elif isinstance(msg, AIMessage):
            history_text += f"Бот: {msg.content}\n"

    full_input = f"""
{SYSTEM_PROMPT}

История:
{history_text}

Вопрос:
Подумай и ответь: {question} на сайте newkey.ru!
"""

    try:
        response = client.responses.create(
            model=f"gpt://{YANDEX_FOLDER_ID}/{YANDEX_MODEL}",
            input=full_input,
            tools=[
                {
                    "type": "web_search",
                    "filters": {
                        "allowed_domains": ["newkey.ru"]
                    }
                }
            ],
            temperature=0.2,
            max_output_tokens=800
        )

        return response.output_text.strip()

    except Exception as e:
        print(f"Ошибка: {e}")
        return "Ошибка генерации ответа"


# =====================================================
# 💬 MEMORY
# =====================================================
chat_histories: Dict[str, List] = {}
MAX_HISTORY = 6


# =====================================================
# 🚀 MAIN LOGIC
# =====================================================
def ask_assistant(user_id: str, question: str) -> str:
    history = chat_histories.get(user_id, [])

    answer = generate_answer(question, history)

    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=answer))
    chat_histories[user_id] = history[-MAX_HISTORY * 2:]

    return answer


# =====================================================
# 🖥️ CLI
# =====================================================
if __name__ == "__main__":
    print("🤖 Бот Newkey запущен")
    user_id = "test_user"

    while True:
        q = input("\n❓ ")
        if q.lower() in ("exit", "quit"):
            break

        print("\n🤖", ask_assistant(user_id, q))
