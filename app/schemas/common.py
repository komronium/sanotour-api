from pydantic import BaseModel


class Translations(BaseModel):
    uz: str | None = None
    ru: str | None = None
    en: str | None = None
