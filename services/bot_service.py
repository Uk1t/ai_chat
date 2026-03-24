import os
import re
from typing import List, Dict, Optional
from dotenv import load_dotenv

from services.main_data import ProductCatalogLoader
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from openai import OpenAI  # Для web search

load_dotenv()

# 🧠 SYSTEM PROMPT
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

# 📦 ЗАГРУЗКА КАТАЛОГА
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

# 🔍 ПОИСК SKU
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

# 🔧 УТИЛИТЫ
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

def get_last_sku_context(history: List) -> Optional[str]:
    """Ищем последний показанный SKU в истории"""
    for msg in reversed(history):
        text = msg.content or ""
        for candidate in re.findall(r"\b([A-Z0-9\-]+)\b", text):
            if candidate.lower() in sku_index:
                return candidate.lower()
    return None

# 🤖 LLM
llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0.2,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

# 🌐 SEARCH по интернету (для терминов)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def search_internet(question: str) -> str:
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

# История
chat_histories: Dict[str, List] = {}

# 🚀 ЛОГИКА
def ask_assistant(user_id: str, question: str) -> str:
    history = chat_histories.get(user_id, [])
    question_lower = question.lower()
    is_definition_query = any(word in question_lower for word in ["что такое", "определение", "термин", "объясни"])

    # 1️⃣ Поиск по SKU в вопросе
    product = search_by_sku(question)
    if product:
        context = "🎯 Точное совпадение:\n" + format_product(product)
        messages = [SystemMessage(content=SYSTEM_PROMPT)]
        messages.extend(history[-6:])  # последние 3 пары
        messages.append(HumanMessage(content=question))
        messages.append(SystemMessage(content=f"📦 КАТАЛОГ:\n{context}"))
        response = llm.invoke(messages)
        answer = response.content
    else:
        # 2️⃣ Попытка использовать последний SKU из истории
        last_sku = get_last_sku_context(history)
        if last_sku:
            product = sku_index[last_sku]
            # Цена
            if any(word in question_lower for word in ["цена", "стоимость", "заказ"]):
                answer = f"Цена позиции {product['name']} (Арт. {product['id']}): {product['price']} руб."
            # Остаток
            elif any(word in question_lower for word in ["остаток", "наличие", "сколько"]):
                answer = f"Остаток позиции {product['name']} (Арт. {product['id']}): {product['stock']}."
            # Аналоги
            elif any(word in question_lower for word in ["аналог", "подобрать"]):
                analogs = [sku_index[a] for a in product.get("analogs_ids", []) if a in sku_index]
                if analogs:
                    answer = "Аналоги:\n" + "\n".join(format_product(a) for a in analogs)
                else:
                    answer = "Аналоги для этой позиции в каталоге не найдены."
            else:
                # Базовый ответ с описанием последнего SKU
                answer = f"{format_product(product)}"
        else:
            # 3️⃣ Категория
            category = determine_category(question, llm)
            if category:
                products = filter_by_category(catalog_memory, category)
                if not products:
                    answer = f"В категории '{category}' ничего не найдено."
                else:
                    lines = [format_product(p) for p in products[:150]]
                    messages = [SystemMessage(content=SYSTEM_PROMPT)]
                    messages.extend(history[-6:])
                    messages.append(HumanMessage(content=question))
                    messages.append(SystemMessage(content=f"📦 Категория: {category}:\n" + "\n".join(lines)))
                    response = llm.invoke(messages)
                    answer = response.content
            else:
                # 4️⃣ Термин
                if is_definition_query:
                    web_info = search_internet(question)
                    answer = f"🌐 Определение из интернета:\n{web_info}" if web_info else "Не удалось найти определение."
                else:
                    answer = "Не могу ответить — вопрос вне темы запорной арматуры."

    # Сохраняем историю
    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=answer))
    chat_histories[user_id] = history[-12:]

    return answer

# CLI
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