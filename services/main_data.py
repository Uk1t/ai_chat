

from typing import List, Optional
from langchain_core.documents import Document
import re
import json


class ProductCatalogLoader:
    def __init__(self, json_file: str):
        with open(json_file, 'r', encoding='utf-8-sig') as f:
            self.data = json.load(f)

        self.analogs_by_product = {p['id']: p.get('analogs_ids', []) for p in self.data}

    # ================= HELPERS =================

    def _detect_product_type(self, name: str, category: str) -> str:
        text = f"{name} {category}".lower()

        if "кран" in text:
            return "кран"
        if "клапан" in text:
            return "клапан"
        if "затвор" in text:
            return "затвор"

        return "прочее"

    def _extract_dn(self, text: Optional[str]) -> Optional[int]:
        if not text:
            return None

        text = text.lower()

        m = re.search(r'dn\s*(\d+)', text)
        if m:
            return int(m.group(1))

        m = re.search(r'(\d+)\s*/\s*(\d+)\s*["”]', text)
        if m:
            num, den = int(m.group(1)), int(m.group(2))
            inches = num / den
            return int(round(inches * 25.4))

        return None

    def _flatten_product(self, product: dict) -> dict:
        safe = {}

        for k, v in product.items():
            if v is None or v == "":
                continue

            if isinstance(v, (str, int, float, bool, list)):
                safe[k.lower()] = v

        return safe

    # ================= MAIN =================

    def create_documents(self) -> List[Document]:
        documents: List[Document] = []

        for product in self.data:
            prod_id = product['id']
            name = product.get('title', 'Без названия')
            stock = product.get('quantity', 0)
            price = product.get('price', 0)
            analogs = product.get('analogs_ids', [])
            category_path = product.get('category', 'Без категории')

            main_category = category_path.split(">")[0].strip()

            product_type = product.get('type') or self._detect_product_type(
                name,
                category_path
            )

            dn = self._extract_dn(name)

            normalized_sizes = [product['size']] if product.get('size') else []

            text_parts = [
                f"Название: {name}",
                f"Категория: {category_path}",
                f"Тип: {product_type}",
                f"DN: {dn if dn else 'не указан'}",
                f"Артикул: {product.get('slug', 'Н/Д')}",
                f"Остаток: {stock}",
                f"Цена: {price}",
            ]

            if normalized_sizes:
                text_parts.append(f"Размер: {', '.join(normalized_sizes)}")

            if analogs:
                text_parts.append("Есть аналоги")

            metadata = {
                **self._flatten_product(product),
                "id": prod_id,
                "name": name,
                "category": category_path,
                "main_category": main_category,
                "product_type": product_type,
                "dn": dn,
                "stock": stock,
                "price": price,
                "sizes": normalized_sizes,
                "has_analogs": bool(analogs),
            }

            documents.append(
                Document(
                    page_content="\n".join(text_parts),
                    metadata=metadata
                )
            )

        return documents


if __name__ == "__main__":
    loader = ProductCatalogLoader('../products_ai.json')
    docs = loader.create_documents()
    print(f"Загружено {len(docs)} товаров")

    if docs:
        print(docs[0].page_content)