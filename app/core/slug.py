import re
import unicodedata

_UZBEK_STRIP = str.maketrans({"ʻ": "", "ʼ": "", "’": "", "'": ""})


def slugify(text: str, *, fallback: str = "item") -> str:
    text = text.translate(_UZBEK_STRIP)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or fallback
