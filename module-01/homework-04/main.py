#FastAPI-сервис для сбора обращений абонентов

import json
import re
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from fastapi import FastAPI
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


APPEALS_PATH = Path(__file__).with_name("appeals.json")

NAME_PATTERN = re.compile(r"^[А-ЯЁ][а-яё]+$")
PHONE_PATTERN = re.compile(r"^(?:\+7|7|8)\d{10}$")
EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
)


class AppealReason(str, Enum):
    """Допустимая причина обращения"""

    NO_NETWORK = "нет доступа к сети"
    PHONE_BROKEN = "не работает телефон"
    NO_MAIL = "не приходят письма"


class Appeal(BaseModel):
    """Обращение абонента"""

    model_config = ConfigDict(populate_by_name=True)

    last_name: str = Field(alias="фамилия")
    first_name: str = Field(alias="имя")
    birth_date: date = Field(alias="дата_рождения")
    phone: str = Field(alias="номер_телефона")
    email: str = Field(alias="e-mail")
    reasons: list[AppealReason] = Field(alias="причины_обращения")
    discovered_at: datetime = Field(
        alias="дата_и_время_обнаружения_проблемы"
    )

    @field_validator("last_name", "first_name")
    @classmethod
    def check_person_name(cls, value: str) -> str:
        # Только заглавная кириллица, без цифр и спецсимволов
        if not NAME_PATTERN.fullmatch(value):
            raise ValueError(
                "Значение должно начинаться с заглавной кириллической "
                "буквы и содержать только кириллицу"
            )
        return value

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str) -> str:
        # Убираем пробелы, скобки и дефисы перед проверкой номера
        normalized = re.sub(r"[\s()\-]", "", value)
        if not PHONE_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Номер должен быть в формате +7XXXXXXXXXX, "
                "7XXXXXXXXXX или 8XXXXXXXXXX"
            )
        return normalized

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        # Адрес должен быть вида name@domain.ton
        if not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Некорректный адрес электронной почты")
        return value

    @field_validator("birth_date")
    @classmethod
    def check_birth_date(cls, value: date) -> date:
        # Дата рождения не может быть в будущем
        if value > date.today():
            raise ValueError("Дата рождения не может быть в будущем")
        return value

    @field_validator("discovered_at")
    @classmethod
    def check_discovered_at(cls, value: datetime) -> datetime:
        # Сравниваем с текущим временем в том же часовом поясе
        if value.tzinfo is None:
            now = datetime.now()
        else:
            now = datetime.now(value.tzinfo)
        if value > now:
            raise ValueError(
                "Дата и время обнаружения проблемы не могут быть "
                "в будущем"
            )
        return value

    @field_validator("reasons", mode="before")
    @classmethod
    def check_reasons(cls, value: object) -> object:
        # В запросе одна или несколько разных причин из списка.
        if not isinstance(value, list) or not value:
            raise ValueError(
                "Нужно указать хотя бы одну причину обращения"
            )
        allowed = {reason.value for reason in AppealReason}
        if any(item not in allowed for item in value):
            raise ValueError(
                "Допустимые причины: нет доступа к сети, "
                "не работает телефон, не приходят письма"
            )
        if len(value) != len(set(value)):
            raise ValueError("Причины обращения не должны повторяться")
        return value

    @model_validator(mode="after")
    def check_discovery_after_birth(self) -> "Appeal":
        # Проблему нельзя обнаружить раньше даты рождения.
        discovered = self.discovered_at
        if discovered.tzinfo is not None:
            discovered = discovered.astimezone().replace(tzinfo=None)
        if discovered.date() < self.birth_date:
            raise ValueError(
                "Дата обнаружения проблемы не может быть раньше "
                "даты рождения"
            )
        return self


app = FastAPI(title="Сбор обращений абонентов")


def save_appeal(appeal: Appeal) -> None:
    # Пишем переданные атрибуты в json рядом с приложением
    APPEALS_PATH.write_text(
        json.dumps(
            appeal.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


@app.post("/appeals/", response_model=Appeal, status_code=201)
def create_appeal(appeal: Appeal) -> Appeal:
    # Принимаем обращение и сохраняем на диск
    save_appeal(appeal)
    return appeal
