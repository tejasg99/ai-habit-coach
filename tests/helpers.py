def bearer(tokens: dict, key: str = "access_token") -> dict:
    return {"Authorization": f"Bearer {tokens[key]}"}