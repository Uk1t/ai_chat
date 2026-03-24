import os
import re
from typing import List, Dict, Optional
from dotenv import load_dotenv

from services.main_data import ProductCatalogLoader
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

# ================= LOAD CATALOG =================

print("📦 Загружаем каталог...")
loader = ProductCatalogLoader("products_ai.json")
docs = loader.create_documents()

catalog: List[dict] = []
sku_index: Dict[str, dict] = {}

for d in docs:
    m = d.metadata
    item = {
        "id": str(m.get("id")),
        "name": m.get("name") or m.get("title"),
        "category": m.get("category", ""),
        "price": m.get("price"),
        "stock": m.get("stock") or m.get("quantity", 0),
        "size": str(m.get("sizes") or m.get("size") or "").lower(),
        "analogs_ids": m.get("analogs_ids", []),
    }
    catalog.append(item)

    if item["id"]:
        sku_index[item["id"].lower()] = item

print(f"✅ Загружено: {len(catalog)} товаров")

# ================= HELPERS =================

def extract_sku(text: str) -> Optional[str]:
    match = re.search(r'\b([A-Z0-9\-*/]+)\b', text.upper())
    if match:
        sku = match.group(1).lower()
        if sku in sku_index:
            return sku
    return None


def search_by_name(text: str) -> Optional[dict]:
    text = text.lower()

    best_match = None
    best_score = 0

    for p in catalog:
        name = p["name"].lower()

        score = 0
        for word in text.split():
            if len(word) > 3 and word in name:
                score += 1

        if score > best_score:
            best_score = score
            best_match = p

    if best_score >= 2:
        return best_match

    return None


def detect_dn(text: str) -> Optional[str]:
    match = re.search(r'\b(?:dn)?\s?(\d{2,4})\b', text.lower())
    return match.group(1) if match else None


def is_price_question(q: str):
    return any(w in q for w in ["цена", "стоимость", "сколько стоит"])


def is_stock_question(q: str):
    return any(w in q for w in ["наличие", "остаток", "сколько есть"])


def is_analogs_question(q: str):
    return any(w in q for w in ["аналог", "подобрать", "варианты"])


def format_product(p: dict) -> str:
    return f"{p['name']} (Арт. {p['id']}) | Ост: {p['stock']} | Цена: {p['price']}"


def filter_by_category(products: List[dict], keyword: str) -> List[dict]:
    keyword = keyword.lower()
    return [p for p in products if keyword in p["category"].lower()]


def filter_by_dn(products: List[dict], dn: str) -> List[dict]:
    return [p for p in products if dn in p["size"]]


# ================= MEMORY =================

chat_histories: Dict[str, List] = {}
user_context: Dict[str, dict] = {}

# ================= CORE =================

def ask_assistant(user_id: str, question: str) -> str:
    history = chat_histories.get(user_id, [])
    ctx = user_context.get(user_id)

    q = question.lower()

    # ========= 1. NEW PRODUCT DETECTION =========
    sku = extract_sku(question)
    product_by_name = search_by_name(question)

    if sku or product_by_name:
        product = sku_index[sku] if sku else product_by_name

        user_context[user_id] = {
            "type": "product",
            "data": product
        }

        if is_price_question(q):
            answer = f"Цена: {product['price']} руб."
        elif is_stock_question(q):
            answer = f"Остаток: {product['stock']} шт."
        else:
            answer = format_product(product)

    # ========= 2. CONTEXT =========
    elif ctx:

        if ctx["type"] == "product":
            p = ctx["data"]

            if is_price_question(q):
                answer = f"Цена: {p['price']} руб."
            elif is_stock_question(q):
                answer = f"Остаток: {p['stock']} шт."
            elif is_analogs_question(q):
                analogs = [sku_index[a] for a in p["analogs_ids"] if a in sku_index]
                answer = "\n".join(format_product(a) for a in analogs) if analogs else "Аналоги не найдены."
            else:
                answer = format_product(p)

        elif ctx["type"] == "list":
            products = ctx["data"]

            if is_price_question(q):
                answer = "Цены:\n" + "\n".join(
                    f"{p['id']}: {p['price']} руб." for p in products[:20]
                )
            elif is_stock_question(q):
                answer = "Остатки:\n" + "\n".join(
                    f"{p['id']}: {p['stock']} шт." for p in products[:20]
                )
            else:
                answer = "\n".join(format_product(p) for p in products[:10])

    # ========= 3. SEARCH =========
    else:
        dn = detect_dn(question)

        if "затвор" in q:
            products = filter_by_category(catalog, "затвор")
        elif "кран" in q:
            products = filter_by_category(catalog, "кран")
        elif "клапан" in q:
            products = filter_by_category(catalog, "клапан")
        else:
            return "Не могу ответить — вопрос вне темы запорной арматуры."

        if dn:
            products = filter_by_dn(products, dn)

        if not products:
            return "Ничего не найдено."

        user_context[user_id] = {
            "type": "list",
            "data": products
        }

        answer = "\n".join(format_product(p) for p in products[:10])

    # ========= SAVE =========
    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=answer))
    chat_histories[user_id] = history[-12:]

    return answer


# ================= CLI =================

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