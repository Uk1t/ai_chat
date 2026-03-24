import os
import re
from typing import List, Dict, Optional
from dotenv import load_dotenv

from services.main_data import ProductCatalogLoader
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from openai import OpenAI  # Для web search

load_dotenv()

# =====================================================
# 🧠 SYSTEM PROMPT
# =====================================================
SYSTEM_PROMPT = """
Ты — профессиональный менеджер по продажам трубопроводной арматуры.
Отвечай ТОЛЬКО на основе данных из блока "📦 КАТАЛОГ" или достоверных источников по арматуре.

ПРАВИЛА:
1. Если товар один — дай четкий ответ.
2. Если несколько — перечисли кратко и задай уточнение.
3. Если остаток 0 — напиши "Нет в наличии" и предложи аналоги.
4. Не отвечай на вопросы вне темы запорной арматуры.
"""

KEY_CATEGORIES = [
    "Краны шаровые", "Дисковые затворы", "Краны с приводами в сборе",
    "Фитинги", "Клапаны электромагнитные", "Задвижки и вентили",
    "Обратные клапаны", "Приводы", "Фильтры", "Фланцы", "Крепеж",
    "Трубы", "Пресс-фитинги", "Компенсаторы (Вибровставки)",
    "Запорная арматура высокого давления", "Насосы", "Щитовые затворы",
    "Регулирующая арматура", "Пищевая арматура", "Криогенная арматура",
    "Комплектующие"
]

# =====================================================
# 📦 ЗАГРУЗКА КАТАЛОГА
# =====================================================
print("📦 Загружаем каталог...")
loader = ProductCatalogLoader("products_ai.json")
all_docs = loader.create_documents()

catalog_memory = []
sku_index: Dict[str, dict] = {}

for d in all_docs:
    meta = d.metadata
    item = {
        "id": str(meta.get("id")),
        "name": meta.get("name") or meta.get("title"),
        "category": meta.get("category", ""),
        "main_category": meta.get("category", "").split(">")[0].strip(),
        "price": meta.get("price"),
        "stock": meta.get("stock") or meta.get("quantity", 0),
        "type": meta.get("product_type") or meta.get("type"),
        "size": meta.get("sizes") or meta.get("size"),
        "manufacturer": meta.get("manufacturer"),
        "analogs_ids": meta.get("analogs_ids", []),
    }
    catalog_memory.append(item)
    sku = item["id"].lower()
    if sku:
        sku_index[sku] = item

print(f"✅ Товаров: {len(catalog_memory)}, SKU в индексе: {len(sku_index)}")

# =====================================================
# 🔍 ПОИСК SKU
# =====================================================
def extract_sku(query: str) -> Optional[str]:
    patterns = [
        r'\b([A-Z]{2,}-?[A-Z0-9/]{3,})\b',
        r'\b([A-Z]{1,}\d{3,})\b',
        r'\b(\d{4,}[A-Z]?)\b',
    ]
    query = query.upper()
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            return match.group(1).lower()
    return None

def search_by_sku(query: str) -> Optional[dict]:
    sku = extract_sku(query)
    if sku and sku in sku_index:
        return sku_index[sku]
    return None

# =====================================================
# 🔧 ВСПОМОГАТЕЛЬНЫЕ
# =====================================================
def filter_by_category(products: List[dict], category: str) -> List[dict]:
    return [p for p in products if p["main_category"] == category]

def format_product(p: dict) -> str:
    analogs = " | 🔁 аналоги" if p.get("analogs_ids") else ""
    return f"{p['name']} (Арт. {p['id']}) | Ост: {p['stock']} | Цена: {p['price']}{analogs}"

def determine_category(question: str, llm) -> Optional[str]:
    prompt = (
        f"Определи категорию товара:\nЗапрос: {question}\n\n"
        "Категории:\n" + "\n".join(KEY_CATEGORIES) +
        "\n\nОтветь ТОЛЬКО названием категории или 'Нет'."
    )
    try:
        res = llm.invoke([HumanMessage(content=prompt)])
        answer = res.content.strip()
        return answer if answer in KEY_CATEGORIES else None
    except:
        return None

# =====================================================
# 🤖 LLM
# =====================================================
llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0.2,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

# =====================================================
# 🌐 INTERNET SEARCH (только арматура)
# =====================================================
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def search_internet(question: str) -> str:
    """
    Использует OpenAI Responses API с web_search инструментом.
    Ограничиваем поиск только по терминам и стандартам арматуры.
    """
    try:
        response = client.responses.create(
            model="gpt-5",
            tools=[{"type": "web_search"}],
            input=f"Найди достоверное определение по запорной арматуре: {question}"
        )
        result = ""
        for item in response.output:
            if item.type == "message":
                for c in item.content:
                    if c.type == "output_text":
                        result += c.text
        return result.strip()
    except Exception as e:
        return f"Не удалось получить информацию из интернета. Ошибка: {e}"

# =====================================================
# 💬 ИСТОРИЯ
# =====================================================
chat_histories: Dict[str, List] = {}
MAX_HISTORY = 6

# =====================================================
# 🚀 ОСНОВНАЯ ЛОГИКА
# =====================================================
def ask_assistant(user_id: str, question: str) -> str:
    history = chat_histories.get(user_id, [])
    question_lower = question.lower()
    is_definition_query = any(word in question_lower for word in ["что такое", "определение", "термин", "объясни"])

    # 1️⃣ Поиск по SKU
    product = search_by_sku(question)
    if product:
        context = "🎯 Точное совпадение:\n" + format_product(product)
        messages_to_send = [SystemMessage(content=SYSTEM_PROMPT)]
        # Берем последние 3 пары сообщений (Human+AI), максимум 6 элементов
        messages_to_send.extend(history[-6:])
        # Добавляем текущий вопрос
        messages_to_send.append(HumanMessage(content=question))
        # Добавляем контекст по SKU
        messages_to_send.append(SystemMessage(content=f"📦 КАТАЛОГ:\n{context}"))
        response = llm.invoke(messages_to_send)
        answer = response.content
    else:
        # 2️⃣ Поиск по категории
        category = determine_category(question, llm)
        if category:
            products = filter_by_category(catalog_memory, category)
            if not products:
                answer = f"В категории '{category}' ничего не найдено."
            else:
                if len(products) > 150:
                    products = products[:150]
                lines = [format_product(p) for p in products]
                context = f"📁 Категория: {category} ({len(products)} товаров)\n" + "\n".join(lines)
                messages_to_send = [SystemMessage(content=SYSTEM_PROMPT)]
                messages_to_send.extend(history[-6:])
                messages_to_send.append(HumanMessage(content=question))
                messages_to_send.append(SystemMessage(content=f"📦 КАТАЛОГ:\n{context}"))
                response = llm.invoke(messages_to_send)
                answer = response.content
        else:
            # 3️⃣ Определение термина (только если явно про термин)
            if is_definition_query:
                web_info = search_internet(question)
                answer = f"🌐 Определение из интернета:\n{web_info}" if web_info else "Не удалось найти определение."
            else:
                # 4️⃣ Вне темы
                answer = "Не могу ответить — вопрос вне темы запорной арматуры."

    # Сохраняем историю
    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=answer))
    # Храним последние 12 сообщений (6 пар)
    chat_histories[user_id] = history[-12:]
    return answer

# =====================================================
# 🖥️ CLI
# =====================================================
if __name__ == "__main__":
    print("🤖 Бот готов. Введите 'exit'")
    user_id = "test_user"
    while True:
        q = input("\n❓ ").strip()
        if q.lower() in ("exit", "quit"):
            break
        try:
            print("\n🤖", ask_assistant(user_id, q))
        except Exception as e:
            print("Ошибка:", e)