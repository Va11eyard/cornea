import re


def normalize_kz_ru_phone(raw: str) -> tuple[str, str | None]:
    if raw is None:
        return "", None
    s = raw.strip()
    if not s:
        return "", None

    digits = re.sub(r"\D", "", s)
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "7":
        pass
    else:
        return s, (
            "Некорректный телефон. Укажите 10 цифр номера или с кодом +7 / 8, "
            "например +7 (700) 123-45-67"
        )

    if len(digits) != 11 or digits[0] != "7":
        return s, "Номер должен начинаться с +7 или 8 и содержать 11 цифр (с кодом страны)."

    return f"+7{digits[1:]}", None
