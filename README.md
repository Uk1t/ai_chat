Для запуска чата нужен test.json c товарами
.env нужно положить переменную 
OPENAI_API_KEY= ''


Пример одного товара

    {
        "id": 6957,
        "title": "Кран шаровый фланцевый (2PC), AISI304 DN 150 (6\"), c односторонним пневмоприводом AT140S",
        "slug": "kran-sharovyi-flantsevyi-2pc-aisi304-dn-150-6-c-odnostoronnim-pnevmoprivodom-at140s",
        "price": 116658.0,
        "old_price": null,
        "sale": 0,
        "quantity": 0,
        "size": "6\" (DN150)",
        "steel": "AISI304 (CF8)",
        "type": "фланцевый",
        "manufacturer": null,
        "pressure": "PN10",
        "category": "Краны с приводами в сборе > Краны фланцевые с пневматическими приводами в сборе > Краны фланцевые двусоставные с односторонним пневмоприводом",
        "ozon_link": null,
        "3d_model_url": null,
        "analogs_ids": [],
        "is_new": false,
        "is_hit": false,
        "is_stock": false,
        "weight_kg": 55.1
    },

Пример в бд на выходе             
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

Проект работает на python 3.13

Для запуска:
 uvicorn main:app --reload                                            
