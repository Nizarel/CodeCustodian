import hashlib


def insecure_eval(user_expression: str) -> int:
    return eval(user_expression)


def weak_crypto(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()


def hardcoded_secret() -> str:
    api_key = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    return api_key
