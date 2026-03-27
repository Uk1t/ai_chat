import os
from typing import Dict, List
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from openai import OpenAI

load_dotenv()

# =====================================================
# 🧠 SYSTEM PROMPT
# =====================================================
SYSTEM_PROMPT = """
Ты — менеджер по продажам трубопроводной арматуры компании Newkey.

Ты работаешь ТОЛЬКО с переданными данными с сайта newkey.ru.
Любая информация вне этих данных запрещена.

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
Наличие: ...
Цена: ...

Если несколько товаров — вывести не более 5 и написать "Есть больше вариантов, уточните параметры".
"""

# =====================================================
# 🤖 LLM
# =====================================================
llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0.2,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =====================================================
# 🔎 ПОИСК ПО САЙТУ NEWKEY
# =====================================================
def search_site(question: str) -> str:
    try:
        query = f"site:newkey.ru {question} (товар OR купить OR артикул)"
        response = client.responses.create(
            model="gpt-5",
            tools=[{"type": "web_search"}],
            input=query
        )
        result = ""
        for item in response.output:
            if item.type == "message":
                for c in item.content:
                    if c.type == "output_text":
                        result += c.text
        return result.strip()
    except Exception:
        return ""

# =====================================================
# 🧠 ГЕНЕРАЦИЯ ОТВЕТА
# =====================================================
def generate_answer(question: str, site_text: str, history: List) -> str:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=f"📄 ДАННЫЕ С САЙТА newkey.ru:\n{site_text[:10000]}")  # больше контекста
    ]
    messages.extend(history[-6:])
    messages.append(HumanMessage(content=question))

    response = llm.invoke(messages)
    return response.content

# =====================================================
# 💬 ИСТОРИЯ
# =====================================================
chat_histories: Dict[str, List] = {}
MAX_HISTORY = 6

# =====================================================
# 🚀 УНИВЕРСАЛЬНАЯ ЛОГИКА
# =====================================================
def ask_assistant(user_id: str, question: str) -> str:
    history = chat_histories.get(user_id, [])

    # 1️⃣ Поиск на сайте
    site_text = search_site(question)

    # 2️⃣ Если данные найдены — генерируем ответ
    if site_text and len(site_text) > 50:
        answer = generate_answer(question, site_text, history)
    else:
        answer = "Не удалось найти информацию на сайте newkey.ru"

    # 3️⃣ Сохраняем историю диалога
    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=answer))
    chat_histories[user_id] = history[-MAX_HISTORY * 2:]

    return answer

# =====================================================
# 🖥️ CLI
# =====================================================
if __name__ == "__main__":
    print("🤖 Универсальный бот Newkey готов")

    user_id = "test_user"

    while True:
        q = input("\n❓ ")
        if q.lower() in ("exit", "quit"):
            break
        print("\n🤖", ask_assistant(user_id, q))