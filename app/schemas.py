from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator

TaskStatus = Literal["in_progress", "completed"]


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    expeditor_id: int = Field(gt=0)
    description: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    status: TaskStatus = "in_progress"
    eta: datetime | None = None

    @field_validator("eta")
    @classmethod
    def normalize_eta(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("eta must include a timezone offset")
        return value.astimezone(timezone.utc) if value is not None else None

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class TaskResponse(TaskCreate):
    id: int
    created_at: datetime


class TaskPage(BaseModel):
    tasks: list[TaskResponse]
    total: int
    page: int
    per_page: int
    expeditor_counts: dict[str, int]


class Token(BaseModel):
    access_token: str
    token_type: str
