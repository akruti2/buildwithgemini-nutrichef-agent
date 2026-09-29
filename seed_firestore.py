import sys
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-5d484fa32047"

def seed():
    db = firestore.Client(project=PROJECT_ID)
    recipes_ref = db.collection("recipes")

    seed_recipes = [
        {
            "id": "lemon-herb-grilled-salmon",
            "title": "Lemon Herb Grilled Salmon & Asparagus",
            "description": "Wild-caught salmon fillet grilled with fresh dill, lemon zest, garlic, and paired with roasted asparagus.",
            "dietary_tags": ["keto", "gluten-free", "pescatarian", "high-protein", "dairy-free"],
            "calories": 480,
            "macros": {"protein_g": 42, "carbs_g": 6, "fat_g": 32},
            "prep_time_minutes": 10,
            "cook_time_minutes": 15,
            "ingredients": [
                "6 oz salmon fillet",
                "1 bunch fresh asparagus",
                "1 tbsp olive oil",
                "1 lemon (sliced & juiced)",
                "2 cloves garlic (minced)",
                "1 tbsp fresh dill",
                "Salt & black pepper"
            ],
            "instructions": [
                "Preheat grill or cast iron pan to medium-high.",
                "Toss asparagus in half of the olive oil, salt, and pepper.",
                "Season salmon with remaining oil, minced garlic, lemon juice, dill, salt, and pepper.",
                "Grill salmon for 4-5 minutes per side until flaky. Grill asparagus for 6-8 minutes until tender-crisp.",
                "Serve immediately with fresh lemon slices."
            ]
        },
        {
            "id": "mediterranean-quinoa-buddha-bowl",
            "title": "Mediterranean Quinoa & Chickpea Power Bowl",
            "description": "Hearty vegan power bowl packed with spiced chickpeas, fluffy quinoa, cucumber, cherry tomatoes, and lemon tahini dressing.",
            "dietary_tags": ["vegan", "vegetarian", "gluten-free", "high-fiber", "dairy-free"],
            "calories": 520,
            "macros": {"protein_g": 19, "carbs_g": 72, "fat_g": 18},
            "prep_time_minutes": 15,
            "cook_time_minutes": 20,
            "ingredients": [
                "1 cup cooked quinoa",
                "1 cup canned chickpeas (rinsed and drained)",
                "1 cup cherry tomatoes (halved)",
                "1 English cucumber (diced)",
                "1/4 cup kalamata olives (pitted)",
                "2 tbsp tahini",
                "1 tbsp fresh lemon juice",
                "1 tsp ground cumin",
                "1 tbsp extra virgin olive oil"
            ],
            "instructions": [
                "Roast chickpeas with olive oil, cumin, salt, and pepper at 400°F (200°C) for 20 minutes until crunchy.",
                "Whisk tahini, lemon juice, warm water, and a pinch of salt to form a creamy dressing.",
                "Assemble bowls with quinoa base, roasted chickpeas, tomatoes, cucumber, and olives.",
                "Drizzle generously with tahini dressing."
            ]
        },
        {
            "id": "turkey-avocado-cauliflower-skillet",
            "title": "Fiesta Ground Turkey & Cauliflower Rice Skillet",
            "description": "Lean ground turkey sautéed with taco spices, riced cauliflower, bell peppers, topped with fresh avocado and cilantro.",
            "dietary_tags": ["keto", "gluten-free", "dairy-free", "high-protein", "low-carb"],
            "calories": 410,
            "macros": {"protein_g": 36, "carbs_g": 12, "fat_g": 24},
            "prep_time_minutes": 10,
            "cook_time_minutes": 15,
            "ingredients": [
                "1 lb lean ground turkey (93/7)",
                "3 cups riced cauliflower",
                "1 red bell pepper (diced)",
                "1/2 yellow onion (diced)",
                "1 avocado (cubed)",
                "1 tbsp chili powder",
                "1 tsp ground cumin",
                "1/4 cup fresh cilantro (chopped)",
                "1 lime (cut into wedges)"
            ],
            "instructions": [
                "Brown ground turkey with onion and bell pepper in a large skillet over medium heat.",
                "Add chili powder, cumin, salt, pepper, and 2 tbsp water; stir for 2 minutes.",
                "Add riced cauliflower and sauté for 4-5 minutes until tender.",
                "Top with diced avocado, cilantro, and freshly squeezed lime juice."
            ]
        },
        {
            "id": "overnight-chia-protein-pudding",
            "title": "Vanilla Berry Overnight Chia Protein Pudding",
            "description": "Antioxidant-rich chia seed pudding infused with plant protein, almond milk, and topped with fresh blueberries and almond butter.",
            "dietary_tags": ["vegetarian", "gluten-free", "dairy-free", "high-fiber"],
            "calories": 360,
            "macros": {"protein_g": 22, "carbs_g": 28, "fat_g": 18},
            "prep_time_minutes": 5,
            "cook_time_minutes": 0,
            "ingredients": [
                "3 tbsp chia seeds",
                "1 scoop vanilla plant protein powder",
                "1 cup unsweetened almond milk",
                "1/2 cup fresh blueberries",
                "1 tbsp natural almond butter",
                "1/2 tsp pure vanilla extract"
            ],
            "instructions": [
                "In a mason jar, vigorously mix chia seeds, protein powder, vanilla, and almond milk.",
                "Let sit for 10 minutes, stir once more to avoid clumping, then refrigerate for at least 4 hours (or overnight).",
                "Top with fresh blueberries and a drizzle of almond butter before serving."
            ]
        }
    ]

    for item in seed_recipes:
        doc_id = item["id"]
        recipes_ref.document(doc_id).set(item)
        print(f"Seeded recipe: {item['title']} (ID: {doc_id})")

    print("\nSuccessfully seeded recipes collection!")

if __name__ == "__main__":
    seed()
