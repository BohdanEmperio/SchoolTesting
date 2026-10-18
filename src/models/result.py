import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TestResult:
    """Модель результата тестирования"""
    id: uuid.UUID
    session_id: uuid.UUID
    overall_risk_level: Optional[str]
    overall_risk_score: Optional[int]
    summary: Optional[str]
    is_processed: bool = False
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_db(cls, row: tuple) -> 'TestResult':
        return cls(
            id=row[0],
            session_id=row[1],
            overall_risk_level=row[2],
            overall_risk_score=row[3],
            summary=row[4],
            is_processed=row[5] if len(row) > 5 else False,
            created_at=row[6] if len(row) > 6 else None
        )