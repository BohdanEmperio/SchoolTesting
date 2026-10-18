import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Class:
    """Модель класса"""
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    class_name: str
    grade_level: int
    letter: str
    homeroom_teacher: Optional[str]
    is_active: bool = True
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_db(cls, row: tuple) -> 'Class':
        return cls(
            id=row[0],
            school_id=row[1],
            academic_year_id=row[2],
            class_name=row[3],
            grade_level=row[4],
            letter=row[5],
            homeroom_teacher=row[6],
            is_active=row[7],
            created_at=row[8] if len(row) > 8 else None
        )