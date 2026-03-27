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
ВАЖНО! Ответ должен быть структурированный HTML!
Ты — менеджер по продажам трубопроводной арматуры компании Newkey.

Ты работаешь ТОЛЬКО с переданными данными с сайта newkey.ru.
Любая информация вне этих данных запрещена.

========================
СТРОГИЕ ПРАВИЛА
========================

1. ЗАПРЕЩЕНО придумывать:
- товары
- характеристики
- цены
- наличие
- артикулы

2. ЗАПРЕЩЕНО:
- делать предположения ("возможно", "скорее всего", "обычно")
- объяснять расхождения цен
- объединять данные из разных источников
- интерпретировать данные

3. ЦЕНА:
- указывай ТОЛЬКО если она явно есть в тексте
- выводи цену ТОЧНО как в тексте
- если найдено несколько цен — перечисли их без объяснений
- если цены нет — напиши: "Цена не указана"

4. НАЛИЧИЕ:
- указывай только если явно есть
- если нет информации — пиши: "Наличие не указано"

5. ЕСЛИ НЕТ ДАННЫХ:
- пиши: "Не удалось найти информацию на сайте newkey.ru"
- НЕ ПЫТАЙСЯ ОТВЕТИТЬ ИЗ ЗНАНИЙ

6. ЕСЛИ НЕСКОЛЬКО ТОВАРОВ:
- перечисли кратко
- задай уточняющий вопрос

7. ЕСЛИ ВОПРОС НЕ ПРО АРМАТУРУ:
- ответ: "По этому вопросу лучше связаться с менеджером"

8. СТИЛЬ:
- кратко
- без лишнего текста
- без “воды”
- как менеджер

9. ЗАПРЕЩЕНО:
- предлагать оформить заказ
- предлагать оставить заявку
- придумывать акции, скидки, причины расхождений

10. Если найдено более 5 товаров:
- выведи не более 5
- не пытайся перечислить все
- напиши: "Есть больше вариантов, уточните параметры"

========================
ФОРМАТ ОТВЕТА
========================

Название товара: ...
Характеристики: ...
Наличие: ...
Цена: ...

(если нет данных — явно укажи это)
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
# 🔎 ПОИСК ПО САЙТУ (УЛУЧШЕННЫЙ)
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
        SystemMessage(content=f"📄 ДАННЫЕ С САЙТА newkey.ru:\n{site_text[:5000]}")
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
# 🚀 ОСНОВНАЯ ЛОГИКА (ПРОСТАЯ И СТАБИЛЬНАЯ)
# =====================================================
def ask_assistant(user_id: str, question: str) -> str:
    history = chat_histories.get(user_id, [])

    # 🔎 ВСЕГДА ИЩЕМ НА САЙТЕ
    site_text = search_site(question)

    if site_text and len(site_text) > 80:
        answer = generate_answer(question, site_text, history)
    else:
        answer = "Не удалось найти информацию на сайте. Могу передать вас менеджеру."

    # сохраняем историю
    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=answer))
    chat_histories[user_id] = history[-MAX_HISTORY * 2:]

    return answer

# =====================================================
# 🖥️ CLI
# =====================================================
if __name__ == "__main__":
    print("🤖 Бот (поиск по сайту newkey.ru) готов")

    user_id = "test_user"

    while True:
        q = input("\n❓ ")
        if q.lower() in ("exit", "quit"):
            break

        print("\n🤖", ask_assistant(user_id, q))