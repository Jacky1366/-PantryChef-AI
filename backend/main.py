from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List
import openai
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from backend.database import engine, get_db
from backend.models import Base, PantryItem
from backend.schemas import PantryItemCreate, PantryItemResponse, RecipeResponse

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="PantryChef AI",
    description="Smart pantry manager that generates recipes from your ingredients",
    version="1.0.0"
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# Serve the main page
@app.get("/")
async def read_root(request: Request, db: Session = Depends(get_db)):
    """Serve the main HTML page"""
    items = db.query(PantryItem).all()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "items": items}
    )


# API Routes
@app.post("/api/pantry/", response_model=PantryItemResponse)
async def add_pantry_item(
    item: PantryItemCreate,
    db: Session = Depends(get_db)
):
    """Add a new ingredient to the pantry"""
    db_item = PantryItem(
        name=item.name,
        expiry_date=item.expiry_date
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.get("/api/pantry/", response_model=List[PantryItemResponse])
async def get_pantry_items(db: Session = Depends(get_db)):
    """Retrieve all pantry items"""
    items = db.query(PantryItem).all()
    return items


@app.delete("/api/pantry/{item_id}")
async def delete_pantry_item(
    item_id: int,
    db: Session = Depends(get_db)
):
    """Remove an item from the pantry"""
    item = db.query(PantryItem).filter(PantryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    db.delete(item)
    db.commit()
    return {"message": "Item deleted successfully", "id": item_id}


@app.post("/api/generate-recipe/", response_model=RecipeResponse)
async def generate_recipe(db: Session = Depends(get_db)):
    """Generate a recipe using AI based on pantry items"""
    # Get all pantry items
    items = db.query(PantryItem).all()
    
    if not items:
        raise HTTPException(
            status_code=400,
            detail="Pantry is empty. Please add some ingredients first!"
        )
    
    # Separate expiring and regular ingredients
    today = datetime.now().date()
    expiring_soon = []
    all_ingredients = []
    
    for item in items:
        all_ingredients.append(item.name)
        if item.expiry_date:
            days_until_expiry = (item.expiry_date - today).days
            if days_until_expiry <= 3:
                expiring_soon.append(item.name)
    
    # Create AI prompt
    if expiring_soon:
        prompt = f"""You are a creative chef. Generate ONE delicious recipe.

MUST USE (expiring soon - HIGH PRIORITY):
{', '.join(expiring_soon)}

ALSO AVAILABLE:
{', '.join([i for i in all_ingredients if i not in expiring_soon])}

Requirements:
- You MUST use at least 2 of the expiring ingredients
- Recipe should be practical and take 30 minutes or less
- Include portions for 2 people
- Provide clear step-by-step instructions
- Include a recipe name as the first line"""
    else:
        prompt = f"""You are a creative chef. Generate ONE delicious recipe.

AVAILABLE INGREDIENTS:
{', '.join(all_ingredients)}

Requirements:
- Recipe should be practical and take 30 minutes or less
- Include portions for 2 people
- Provide clear step-by-step instructions
- Include a recipe name as the first line"""
    
    # Call OpenAI API
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful chef who creates practical, delicious recipes."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.8,
            max_tokens=500
        )
        
        recipe_text = response.choices[0].message.content
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recipe: {str(e)}"
        )
    
    return RecipeResponse(
        recipe=recipe_text,
        expiring_items=expiring_soon,
        total_items=len(all_ingredients),
        items_used=len(expiring_soon) if expiring_soon else len(all_ingredients)
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "PantryChef AI is running!"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)