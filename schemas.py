from pydantic import BaseModel, Field
from datetime import date
from typing import Optional, List


class PantryItemBase(BaseModel):
    """Base schema for pantry items"""
    name: str = Field(..., min_length=1, max_length=100, description="Name of the ingredient")
    expiry_date: Optional[date] = Field(None, description="Expiry date of the ingredient")


class PantryItemCreate(PantryItemBase):
    """Schema for creating a new pantry item"""
    pass


class PantryItemResponse(PantryItemBase):
    """Schema for pantry item response"""
    id: int
    
    class Config:
        from_attributes = True  # Updated from orm_mode for Pydantic v2


class RecipeResponse(BaseModel):
    """Schema for recipe generation response"""
    recipe: str = Field(..., description="Generated recipe text")
    expiring_items: List[str] = Field(default=[], description="List of expiring ingredients used")
    total_items: int = Field(..., description="Total number of pantry items")
    items_used: int = Field(..., description="Number of items used in the recipe")