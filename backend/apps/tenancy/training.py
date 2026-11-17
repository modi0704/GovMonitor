"""Identify only the untouched agencies supplied by the optional development seed."""

BUILT_IN_TRAINING = {
    "sample-ministry": ("Sample Ministry", "admin@sample-ministry.demo"),
    "sample-bureau": ("Sample Bureau", "admin@sample-bureau.demo"),
}


def is_builtin_training(code: str, name: str, user_emails: list[str]) -> bool:
    expected = BUILT_IN_TRAINING.get(code)
    return bool(expected and name == expected[0] and set(user_emails) == {expected[1]})
