import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class PsychologicalTest:
    """Модель психологического теста"""
    id: uuid.UUID
    test_code: str
    test_name: str
    description: Optional[str]
    version: Optional[str]
    questions_count: int = 0
    is_active: bool = True
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_db(cls, row: tuple) -> 'PsychologicalTest':
        return cls(
            id=row[0],
            test_code=row[1],
            test_name=row[2],
            description=row[3],
            version=row[4] if len(row) > 4 else '1.0',
            questions_count=row[5] if len(row) > 5 else 0,
            is_active=row[6] if len(row) > 6 else True,
            created_at=row[7] if len(row) > 7 else None
        )