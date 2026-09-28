import re

_PLATE = re.compile(r"(?<!\d)(\d{2,3})\s*([가-힣])\s*(\d{4})(?!\d)")


def mask_license_plates(text: str) -> str:
    return _PLATE.sub(lambda match: f"{match.group(1)}{match.group(2)}****", text)
