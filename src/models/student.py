import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Student:
    """Модель ученика"""
    id: uuid.UUID
    student_code: str
    first_name_enc: bytes
    last_name_enc: bytes
    middle_name_enc: Optional[bytes]
    birth_date: Optional[datetime]
    gender: Optional[str]
    class_id: Optional[uuid.UUID]
    is_active: bool = True
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_db(cls, row: tuple) -> 'Student':
        return cls(
            id=row[0],
            student_code=row[1],
            first_name_enc=row[2],
            last_name_enc=row[3],
            middle_name_enc=row[4],
            birth_date=row[5],
            gender=row[6],
            class_id=row[7],
            is_active=row[8],
            created_at=row[9] if len(row) > 9 else None
        )