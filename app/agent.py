# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import re
from typing import Any, Dict, List, Optional
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google import genai
from google.cloud import firestore, storage
from google.genai import types

try:
    from a2ui.schema.manager import A2uiSchemaManager
    from a2ui.basic_catalog.provider import BasicCatalog
    _HAS_A2UI_SDK = True
except ImportError:
    _HAS_A2UI_SDK = False

from app.a2ui_utils import a2ui_callback

MODEL = "gemini-3.6-flash"

# Hardcoded project ID string for Firestore client and Cloud Storage
PROJECT_ID = "qwiklabs-gcp-03-5d484fa32047"
BUCKET_NAME = "nutrichef-assets-qwiklabs-gcp-03-5d484fa32047"
AGENT_ENGINE_RESOURCE_NAME = "projects/1061460441039/locations/us-east1/reasoningEngines/6954065799032078336"
SANDBOX_RESOURCE_NAME = "projects/1061460441039/locations/us-east1/reasoningEngines/6954065799032078336/sandboxEnvironments/8597732328464187392"
MEMORY_BANK_ID = "6954065799032078336"

db = firestore.Client(project=PROJECT_ID)
storage_client = storage.Client(project=PROJECT_ID)
genai_image_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
sandbox_code_executor = AgentEngineSandboxCodeExecutor(
    sandbox_resource_name=SANDBOX_RESOURCE_NAME,
    agent_engine_resource_name=AGENT_ENGINE_RESOURCE_NAME,
)


# WRITE: after each turn, send the session events to Memory Bank for durable extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


def list_recipes(dietary_tag: Optional[str] = None, max_calories: Optional[int] = None) -> List[Dict[str, Any]]:
    """Lists recipes from the culinary database, optionally filtering by dietary tag or max calories.

    Args:
        dietary_tag: Optional dietary filter (e.g., 'keto', 'vegan', 'gluten-free', 'high-protein').
        max_calories: Optional upper limit on calorie count.

    Returns:
        A list of matching recipe summaries containing ID, title, calories, macros, and dietary tags.
    """
    recipes_ref = db.collection("recipes")
    docs = recipes_ref.stream()

    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id

        if dietary_tag:
            tags = [t.lower() for t in data.get("dietary_tags", [])]
            if dietary_tag.lower() not in tags:
                continue

        if max_calories is not None:
            if data.get("calories", 0) > max_calories:
                continue

        results.append({
            "id": data["id"],
            "title": data.get("title"),
            "description": data.get("description"),
            "dietary_tags": data.get("dietary_tags", []),
            "calories": data.get("calories"),
            "macros": data.get("macros", {}),
            "prep_time_minutes": data.get("prep_time_minutes"),
            "cook_time_minutes": data.get("cook_time_minutes"),
        })
    return results


def get_recipe_details(recipe_id: str) -> Dict[str, Any]:
    """Retrieves full details for a recipe, including ingredients and cooking instructions.

    Args:
        recipe_id: The unique identifier of the recipe (e.g., 'lemon-herb-grilled-salmon').

    Returns:
        A dictionary with complete recipe information or an error message if not found.
    """
    doc = db.collection("recipes").document(recipe_id).get()
    if not doc.exists:
        return {"error": f"Recipe with ID '{recipe_id}' not found."}
    data = doc.to_dict()
    data["id"] = doc.id
    return data


def save_recipe(
    title: str,
    description: str,
    dietary_tags: List[str],
    calories: int,
    protein_g: int,
    carbs_g: int,
    fat_g: int,
    prep_time_minutes: int,
    cook_time_minutes: int,
    ingredients: List[str],
    instructions: List[str],
    recipe_id: Optional[str] = None
) -> Dict[str, Any]:
    """Saves a new recipe or updates an existing recipe in the database.

    Args:
        title: Title of the dish.
        description: Brief appetizing summary of the dish.
        dietary_tags: List of dietary categories (e.g. ['keto', 'high-protein']).
        calories: Total calorie count per serving.
        protein_g: Grams of protein.
        carbs_g: Grams of carbohydrates.
        fat_g: Grams of dietary fat.
        prep_time_minutes: Preparation time in minutes.
        cook_time_minutes: Active cooking time in minutes.
        ingredients: List of ingredients with quantities.
        instructions: Step-by-step preparation steps.
        recipe_id: Optional slug identifier; if omitted, one will be generated from the title.

    Returns:
        Status dictionary confirming creation or update.
    """
    if not recipe_id:
        recipe_id = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

    recipe_data = {
        "id": recipe_id,
        "title": title,
        "description": description,
        "dietary_tags": dietary_tags,
        "calories": calories,
        "macros": {
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fat_g": fat_g
        },
        "prep_time_minutes": prep_time_minutes,
        "cook_time_minutes": cook_time_minutes,
        "ingredients": ingredients,
        "instructions": instructions
    }

    db.collection("recipes").document(recipe_id).set(recipe_data)
    return {"status": "success", "recipe_id": recipe_id, "message": f"Recipe '{title}' saved successfully."}


def calculate_macro_targets(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    activity_level: str = "moderate",
    goal: str = "maintenance"
) -> Dict[str, Any]:
    """Calculates daily calorie needs and macronutrient targets based on personal biometrics.

    Args:
        weight_kg: Body weight in kilograms.
        height_cm: Body height in centimeters.
        age: Age in years.
        gender: 'male' or 'female'.
        activity_level: 'sedentary' (desk job), 'light' (1-3 days/wk), 'moderate' (3-5 days/wk), 'active' (6-7 days/wk).
        goal: 'weight_loss' (500 kcal deficit), 'muscle_gain' (300 kcal surplus), or 'maintenance'.

    Returns:
        A dictionary with BMR, TDEE, target calories, and target grams for protein, carbs, and fat.
    """
    # Mifflin-St Jeor formula for BMR
    if gender.lower().startswith("m"):
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725
    }
    multiplier = activity_multipliers.get(activity_level.lower(), 1.55)
    tdee = bmr * multiplier

    goal_adjustments = {
        "weight_loss": -500,
        "muscle_gain": 300,
        "maintenance": 0
    }
    target_calories = round(tdee + goal_adjustments.get(goal.lower(), 0))

    # Standard balanced macronutrient split: 30% Protein, 40% Carbs, 30% Fat
    # 1g Protein = 4 kcal, 1g Carb = 4 kcal, 1g Fat = 9 kcal
    protein_grams = round((target_calories * 0.30) / 4)
    carbs_grams = round((target_calories * 0.40) / 4)
    fat_grams = round((target_calories * 0.30) / 9)

    return {
        "bmr_kcal": round(bmr),
        "tdee_kcal": round(tdee),
        "target_calories": target_calories,
        "goal": goal,
        "target_macros": {
            "protein_g": protein_grams,
            "carbs_g": carbs_grams,
            "fat_g": fat_grams
        }
    }


def search_global_recipes(query: str) -> List[Dict[str, Any]]:
    """Searches a public global recipe database (TheMealDB) for dishes by ingredient or keyword.

    Args:
        query: Ingredient or dish name (e.g., 'salmon', 'chicken', 'curry', 'pasta').

    Returns:
        A list of recipes with title, category, cuisine origin, ingredients list, instructions snippet, and image URL.
    """
    import json
    import urllib.parse
    import urllib.request

    url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "NutriChef/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return [{"error": f"Failed to fetch global recipes: {str(e)}"}]

    meals = data.get("meals") or []
    results = []
    for meal in meals[:3]:  # Top 3 matching recipes
        ingredients = []
        for i in range(1, 21):
            ing = meal.get(f"strIngredient{i}")
            measure = meal.get(f"strMeasure{i}")
            if ing and ing.strip():
                measure_str = f" ({measure.strip()})" if measure and measure.strip() else ""
                ingredients.append(f"{ing.strip()}{measure_str}")

        results.append({
            "title": meal.get("strMeal"),
            "category": meal.get("strCategory"),
            "cuisine": meal.get("strArea"),
            "image_url": meal.get("strMealThumb"),
            "ingredients": ingredients,
            "instructions": (meal.get("strInstructions") or "")[:400] + "..."
        })
    return results


async def generate_dish_image(dish_name: str, visual_description: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Generates a photorealistic culinary image of a dish using gemini-3.1-flash-lite-image, saves it as an artifact, and uploads to Cloud Storage.

    Args:
        dish_name: Name of the dish (e.g. 'Lemon Herb Grilled Salmon').
        visual_description: Plating and presentation details (e.g. 'Garnished with fresh dill and lemon slices on a rustic ceramic plate').
        tool_context: ADK ToolContext used to save session artifacts.

    Returns:
        A dictionary with public image URL, artifact filename, and status.
    """
    prompt = (
        f"Professional culinary food photography of {dish_name}. "
        f"{visual_description}. "
        "Appetizing, vibrant natural lighting, shallow depth of field, 4k high resolution."
    )

    try:
        response = genai_image_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt
        )
    except Exception as e:
        return {"error": f"Failed to generate image: {str(e)}"}

    image_bytes = None
    mime_type = "image/jpeg"
    for candidate in response.candidates:
        for part in candidate.content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                mime_type = part.inline_data.mime_type or "image/jpeg"
                break
        if image_bytes:
            break

    if not image_bytes:
        return {"error": "No image data returned from image generation model."}

    # Safe slug for filenames
    slug = re.sub(r'[^a-z0-9]+', '-', dish_name.lower()).strip('-')
    ext = "jpg" if "jpeg" in mime_type.lower() else "png"
    filename = f"{slug}.{ext}"

    # 1. Save artifact in Playground's Artifacts panel via tool_context
    artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    await tool_context.save_artifact(
        filename=filename,
        artifact=artifact_part,
        custom_metadata={"dish_name": dish_name, "prompt": prompt}
    )

    # 2. Upload to public Cloud Storage bucket
    bucket = storage_client.bucket(BUCKET_NAME)
    blob_path = f"dishes/{filename}"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_path}"

    return {
        "status": "success",
        "dish_name": dish_name,
        "artifact_filename": filename,
        "image_url": public_url,
        "message": f"Generated image for {dish_name} saved to artifacts and published to {public_url}"
    }


async def generate_dish_video(dish_name: str, scene_description: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Generates a short culinary cooking or plating video for an item in NutriChef's domain using Google's Omni model (gemini-omni-flash-preview) in the global region.
    
    Saves the video with tool_context.save_artifact so it appears in Playground's Artifacts panel,
    and uploads the video bytes to the public Cloud Storage bucket, returning its public https URL.

    Args:
        dish_name: Name of the dish or culinary item (e.g. 'Sizzling Garlic Butter Paneer', 'Avocado Toast Plating').
        scene_description: Detailed visual scene description of motion, steam, or culinary action (e.g. 'A close-up shot of golden paneer cubes sizzling in hot garlic butter with steam rising gently').
        tool_context: ADK ToolContext used to save session artifacts.

    Returns:
        A dictionary with public video URL, artifact filename, and status.
    """
    omni_client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location="global",
    )
    prompt = (
        f"A cinematic culinary video of {dish_name}. {scene_description}. "
        "Appetizing, professional studio lighting, continuous smooth shot, high definition."
    )

    try:
        interaction = omni_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
            response_format={
                "type": "video",
                "duration": "4s",
                "aspect_ratio": "16:9",
            },
        )
    except Exception as e:
        return {"error": f"Failed to generate video with gemini-omni-flash-preview: {str(e)}"}

    video_bytes = None
    mime_type = "video/mp4"

    # Extract video bytes from the interaction response
    if hasattr(interaction, "output_video") and getattr(interaction.output_video, "data", None):
        video_bytes = base64.b64decode(interaction.output_video.data)
    elif hasattr(interaction, "steps") and interaction.steps:
        for step in interaction.steps:
            content_list = getattr(step, "content", []) or []
            for item in content_list:
                item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
                if item_type == "video":
                    data = getattr(item, "data", None) or (item.get("data") if isinstance(item, dict) else None)
                    if data:
                        video_bytes = base64.b64decode(data) if isinstance(data, str) else data
                        break
            if video_bytes:
                break

    if not video_bytes:
        return {"error": "No video data received in interaction response from gemini-omni-flash-preview."}

    # Safe slug for filenames
    slug = re.sub(r'[^a-z0-9]+', '-', dish_name.lower()).strip('-')
    filename = f"{slug}-culinary-demo.mp4"

    # 1. Save artifact in Playground's Artifacts panel via tool_context
    artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
    await tool_context.save_artifact(
        filename=filename,
        artifact=artifact_part,
        custom_metadata={"dish_name": dish_name, "prompt": prompt}
    )

    # 2. Upload to public Cloud Storage bucket
    bucket = storage_client.bucket(BUCKET_NAME)
    blob_path = f"videos/{filename}"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(video_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_path}"

    return {
        "status": "success",
        "dish_name": dish_name,
        "artifact_filename": filename,
        "video_url": public_url,
        "message": f"Generated video for {dish_name} saved to artifacts and published to {public_url}"
    }


_PROMPT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "a2ui_prompt.txt")

if _HAS_A2UI_SDK:
    schema_manager = A2uiSchemaManager(
        version="0.8",
        catalogs=[BasicCatalog.get_config("0.8")],
    )
    instruction = schema_manager.generate_system_prompt(
        role_description=(
            "NutriChef AI, an expert culinary chef and certified nutritionist. "
            "You help users discover delicious, balanced recipes tailored to their dietary goals, restrictions, and macros. "
            "You remember the user's stated personal preferences, dietary restrictions, allergies, and goals across conversations and use them to personalize every recommendation. "
            "You can calculate personal daily caloric and macronutrient targets using calculate_macro_targets, "
            "search your curated database using list_recipes and get_recipe_details, "
            "search the public open-world recipe database using search_global_recipes for broad inspiration, "
            "generate mouth-watering culinary food visuals using generate_dish_image, "
            "generate short cooking and plating videos using generate_dish_video, "
            "and save or update custom recipe creations using save_recipe. "
            "You also have a Python code execution sandbox to perform complex calculations, nutritional simulations, or recipe scaling computations."
        ),
        workflow_description="Analyze the culinary or nutritional request, call relevant tools to get data or generate food images, and return structured UI when appropriate.",
        ui_description=(
            "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
            "Never nest a Card inside a Card. "
            "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
            "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
            "nothing in adk web). "
            "You may include one Image component, but only when you have a public https "
            "URL for the image (for example the URL an image tool returns after uploading "
            "to a public bucket). Set the Image url to that exact https link, for example "
            "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
            "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
            "not have a public URL, add a short Text line noting the image instead. "
            "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
            "headings and emphasis. "
            "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
            "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
        ),
        include_schema=True,
        include_examples=True,
    )
elif os.path.exists(_PROMPT_FILE):
    with open(_PROMPT_FILE, "r", encoding="utf-8") as f:
        instruction = f.read()
else:
    instruction = "NutriChef AI, an expert culinary chef and certified nutritionist."

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=sandbox_code_executor,
    tools=[
        PreloadMemoryTool(),
        calculate_macro_targets,
        list_recipes,
        get_recipe_details,
        search_global_recipes,
        generate_dish_image,
        generate_dish_video,
        save_recipe,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
