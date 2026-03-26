import os
import re
from typing import List, Dict, Optional
from dotenv import load_dotenv

from services.main_data import ProductCatalogLoader
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from openai import OpenAI

load_dotenv()

# =====================================================
# 🧠 SYSTEM PROMPT
# =====================================================
SYSTEM_PROMPT = """
Ты — профессиональный менеджер по продажам трубопроводной арматуры.

Отвечай ТОЛЬКО на основе:
1. 📦 КАТАЛОГА
2. 📄 ДАННЫХ С САЙТА newkey.ru

ПРАВИЛА:
1. Если товар один — дай четкий ответ
2. Если несколько — перечисли кратко и задай уточнение
3. Если остаток 0 — напиши "Нет в наличии" и предложи аналоги
4. Не отвечай вне темы арматуры
5. Если не уверен — предложи связаться с менеджером
"""

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
        "manufacturer": meta.get("manufacturer"),
        "analogs_ids": meta.get("analogs_ids", []),
    }
    catalog_memory.append(item)

    if item["id"]:
        sku_index[item["id"].lower()] = item

print(f"✅ Товаров: {len(catalog_memory)}")

# =====================================================
# 🔍 SKU ПОИСК
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
    return sku_index.get(sku)

# =====================================================
# 🔧 ВСПОМОГАТЕЛЬНЫЕ
# =====================================================
def format_product(p: dict) -> str:
    analogs = " | 🔁 аналоги" if p.get("analogs_ids") else ""
    return f"{p['name']} (Арт. {p['id']}) | Ост: {p['stock']} | Цена: {p['price']}{analogs}"

def filter_by_category(products: List[dict], category: str) -> List[dict]:
    return [p for p in products if p["main_category"] == category]

def determine_category(question: str, llm) -> Optional[str]:
    prompt = (
        f"Определи категорию:\n{question}\n\n"
        "Ответь только названием категории или 'Нет'"
    )
    try:
        res = llm.invoke([HumanMessage(content=prompt)])
        return res.content.strip()
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

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =====================================================
# 🔎 ПОИСК ПО САЙТУ newkey.ru
# =====================================================
def search_site(question: str) -> str:
    try:
        query = f"site:newkey.ru {question}"

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
# 🧠 ГЕНЕРАЦИЯ ОТВЕТА ПО САЙТУ
# =====================================================
def generate_site_answer(question: str, site_text: str) -> str:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=f"📄 ДАННЫЕ С САЙТА:\n{site_text[:4000]}"),
        HumanMessage(content=question)
    ]

    response = llm.invoke(messages)
    return response.content

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

    # 1️⃣ SKU
    product = search_by_sku(question)
    if product:
        context = format_product(product)

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            SystemMessage(content=f"📦 КАТАЛОГ:\n{context}")
        ]
        messages.extend(history[-MAX_HISTORY:])
        messages.append(HumanMessage(content=question))

        answer = llm.invoke(messages).content

    else:
        # 2️⃣ Категория
        category = determine_category(question, llm)

        if category:
            products = filter_by_category(catalog_memory, category)

            if products:
                products = products[:100]
                context = "\n".join([format_product(p) for p in products])

                messages = [
                    SystemMessage(content=SYSTEM_PROMPT),
                    SystemMessage(content=f"📦 КАТАЛОГ:\n{context}")
                ]
                messages.extend(history[-MAX_HISTORY:])
                messages.append(HumanMessage(content=question))

                answer = llm.invoke(messages).content
            else:
                answer = f"В категории '{category}' ничего не найдено"

        else:
            # 3️⃣ 🔎 ПОИСК ПО САЙТУ
            site_text = search_site(question)

            if site_text and len(site_text) > 100:
                answer = generate_site_answer(question, site_text)
            else:
                answer = "Не нашел информации. Могу передать вас менеджеру."

    # сохраняем историю
    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=answer))
    chat_histories[user_id] = history[-MAX_HISTORY * 2:]

    return answer

# =====================================================
# 🖥️ CLI
# =====================================================
if __name__ == "__main__":
    print("🤖 Бот готов")

    user_id = "test_user"

    while True:
        q = input("\n❓ ")
        if q.lower() in ("exit", "quit"):
            break

        print("\n🤖", ask_assistant(user_id, q))