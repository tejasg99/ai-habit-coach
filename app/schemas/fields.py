from typing import Annotated

from pydantic import BeforeValidator, StringConstraints


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


# BeforeValidator runs before max_length check so " " becomes None first
DisplayName = Annotated[
    Annotated[str, StringConstraints(max_length=100)] | None,
    BeforeValidator(_blank_to_none)
]
