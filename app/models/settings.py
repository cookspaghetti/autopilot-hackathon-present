# app/models/settings.py
"""
Settings model for storing application configuration in the database.
This is used for managing things like approved email domains dynamically.
"""

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from ..core.database import Base


class Settings(Base):
    """
    Key-value store for application settings.
    Allows for dynamic configuration without redeployment.
    """

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Settings(key='{self.key}')>"
