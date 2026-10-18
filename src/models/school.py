import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class School:
    """Модель школы"""
    id: uuid.UUID
    school_name: str
    address: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    is_active: bool = True
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_db(cls, row: tuple) -> 'School':
        return cls(
            id=row[0],
            school_name=row[1],
            address=row[2],
            phone=row[3],
            email=row[4],
            is_active=row[5],
            created_at=row[6] if len(row) > 6 else None
        )