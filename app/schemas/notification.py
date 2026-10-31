import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict

_EXPO_TOKEN_RE = re.compile(r"(Exponent|Expo)PushToken\[[A-Za-z0-9_\-]+\]")


def _check_token(value: str) -> str:
    value = value.strip()
    if len(value) > 255 or not _EXPO_TOKEN_RE.fullmatch(value):
        raise ValueError("Not a valid Expo push token")
    return value


class PushTokenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: Annotated[str, AfterValidator(_check_token)]
