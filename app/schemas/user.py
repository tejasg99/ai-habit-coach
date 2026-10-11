from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Input contract
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped != "" else None
        return v


# Output contract
class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    # lets pydantic read fields straight off a SQLAlchemy User object

    id: int
    email: EmailStr
    display_name: str | None
    created_at: datetime