"""Grounded AI Manager API."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..schemas.command_center import (
    AIManagerRequest,
    AIManagerResponse,
    AIManagerToolCall,
)
from ..services.ai_manager import GroundedAIManager

router = APIRouter(prefix="/ai", tags=["AI Manager"])


@router.post("/chat", response_model=AIManagerResponse)
async def chat(payload: AIManagerRequest, db: Session = Depends(get_db)):
    answer = await GroundedAIManager().answer(message=payload.message, db=db)
    return AIManagerResponse(
        response=answer.response,
        tool_calls=[
            AIManagerToolCall(
                id=item.id,
                name=item.name,
                args=item.args,
                result=item.result,
            )
            for item in answer.tool_calls
        ],
    )
