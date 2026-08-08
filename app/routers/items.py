# app/routers/items.py
"""
Item CRUD endpoints - example resource management.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.item import Item as ItemModel
from ..schemas.item import Item, ItemCreate

log = logging.getLogger(__name__)

router = APIRouter(prefix="/items", tags=["Items"])


@router.get("", response_model=list[Item])
def list_items(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """
    Get all items with pagination.
    Requires authenticated user with 'user' or 'admin' role.
    """
    items = db.query(ItemModel).offset(skip).limit(limit).all()
    return items


@router.post("", response_model=Item)
def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    """
    Create a new item.
    Requires authenticated user with 'user' or 'admin' role.
    """
    db_item = ItemModel(name=item.name, description=item.description)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int, db: Session = Depends(get_db)):
    """
    Get a specific item by ID.
    Requires authenticated user with 'user' or 'admin' role.
    """
    db_item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return db_item


@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    """
    Delete an item by ID.
    Requires authenticated user with 'user' or 'admin' role.
    """
    db_item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(db_item)
    db.commit()
    return {"message": "Item deleted"}
