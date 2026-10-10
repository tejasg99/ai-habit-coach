from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Input contract
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)

# Output contract
class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    # lets pydantic read fields straight off a SQLAlchemy User object

    id: int
    email: EmailStr
    display_name: str | None
    created_at: datetime