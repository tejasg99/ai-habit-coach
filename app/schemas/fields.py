from typing import Annotated
from pydantic import BeforeValidator, Field

def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value

# BeforeValidator runs before max_length check so " " becomes None first
DisplayName = Annotated[str | None, BeforeValidator(_blank_to_none), Field(max_length=100)]