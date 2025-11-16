from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List
import os
import markdown
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

from backend.database import engine, get_db
from backend.models import Base, PantryItem
from backend.schemas import PantryItemCreate, PantryItemResponse, RecipeResponse

# -----------------------------
# ✅ 新 OpenAI SDK 导入方式
# -----------------------------
from openai import OpenAI

# -----------------------------
# ✅ 强制加载项目根目录的 .env（100% 成功）
# -----------------------------
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise Exception(f"❌ OPENAI_API_KEY not found. Make sure .env exists at: {env_path}")

# 初始化 OpenAI 客户端
client = OpenAI(api_key=api_key)

# -----------------------------
# Startup
# -----------------------------
Base.metadata.create_all(bind=engine)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "frontend" / "static"
TEMPLATE_DIR = BASE_DIR / "frontend" / "templates"

app = FastAPI(
    title="PantryChef AI",
    description="Smart pantry manager that generates recipes from your ingredients",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
async def read_root(request: Request, db: Session = Depends(get_db)):
    items = db.query(PantryItem).all()
    return templates.TemplateResponse("index.html", {"request": request, "items": items})


@app.post("/api/pantry/", response_model=PantryItemResponse)
async def add_pantry_item(item: PantryItemCreate, db: Session = Depends(get_db)):
    db_item = PantryItem(name=item.name, expiry_date=item.expiry_date)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.get("/api/pantry/", response_model=List[PantryItemResponse])
async def get_pantry_items(db: Session = Depends(get_db)):
    return db.query(PantryItem).all()


@app.delete("/api/pantry/{item_id}")
async def delete_pantry_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(PantryItem).filter(PantryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"message": "Item deleted successfully", "id": item_id}

@app.delete("/api/pantry/")
async def clear_pantry(db: Session = Depends(get_db)):
    db.query(PantryItem).delete()
    db.commit()
    return {"message": "Pantry cleared"}



@app.post("/api/generate-recipe/", response_model=RecipeResponse)
async def generate_recipe(db: Session = Depends(get_db)):
    items = db.query(PantryItem).all()
    if not items:
        raise HTTPException(
            status_code=400,
            detail="Pantry is empty. Please add some ingredients first!",
        )

    today = datetime.now().date()
    expiring_soon: list[str] = []
    all_ingredients: list[str] = []

    for item in items:
        all_ingredients.append(item.name)
        if item.expiry_date:
            days_left = (item.expiry_date - today).days
            if days_left <= 3:
                expiring_soon.append(item.name)

    if expiring_soon:
        prompt = f"""You are a creative chef. Generate ONE delicious recipe.

MUST USE (expiring soon - HIGH PRIORITY):
{', '.join(expiring_soon)}

ALSO AVAILABLE:
{', '.join(i for i in all_ingredients if i not in expiring_soon)}

Requirements:
- You MUST use at least 2 expiring ingredients
- 30 minutes or less cook time
- Portions for 2 people
- Step-by-step instructions
- Start with the recipe name"""
    else:
        prompt = f"""You are a creative chef. Generate ONE delicious recipe.

AVAILABLE INGREDIENTS:
{', '.join(all_ingredients)}

Requirements:
- Practical recipe (30 minutes or less)
- Portions for 2 people
- Step-by-step instructions
- Start with the recipe name"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful chef who creates delicious, practical recipes.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=500,
        )

        recipe_text = response.choices[0].message.content
        recipe_html = markdown.markdown(recipe_text)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recipe: {str(e)}",
        )

    return RecipeResponse(
        recipe=recipe_html,
        expiring_items=expiring_soon,
        total_items=len(all_ingredients),
        items_used=len(expiring_soon) if expiring_soon else len(all_ingredients),
    )


@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "PantryChef AI is running!"}


@app.get("/add-food")
async def add_food_page(request: Request):
    return templates.TemplateResponse("add-food.html", {"request": request})


@app.get("/food")
async def food_page(request: Request):
    return templates.TemplateResponse("food.html", {"request": request})


@app.get("/recipe")
async def recipe_page(request: Request):
    return templates.TemplateResponse("recepie.html", {"request": request})


# -----------------------------
# Run server
# -----------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
