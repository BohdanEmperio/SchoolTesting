import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """Модель пользователя"""
    id: uuid.UUID
    login: str
    email: Optional[str]
    role: str  # 'admin', 'psychologist', 'student'
    school_id: Optional[uuid.UUID]
    is_active: bool = True
    is_verified: bool = True
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_db(cls, row: tuple) -> 'User':
        """Создание объекта из строки БД"""
        return cls(
            id=row[0],
            login=row[1],
            email=row[2],
            role=row[3],
            school_id=row[4],
            is_active=row[5],
            is_verified=row[6],
            created_at=row[7] if len(row) > 7 else None
        )