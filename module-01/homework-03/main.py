"""FastAPI-приложение: асинхронный расчёт квадратов чисел."""

import asyncio
import time

from fastapi import FastAPI
from pydantic import BaseModel, model_validator


app = FastAPI(title="Асинхронный расчёт квадратов")


class CalculateRequest(BaseModel):
    """Список чисел и задержка перед расчётом каждого квадрата."""

    numbers: list[float]
    delays: list[float]

    @model_validator(mode="after")
    def check_pairs(self) -> "CalculateRequest":
        """Проверить длину списков и знак задержек."""
        if len(self.numbers) != len(self.delays):
            raise ValueError(
                "Списки numbers и delays должны быть одной длины"
            )
        if any(delay < 0 for delay in self.delays):
            raise ValueError("Задержки не могут быть отрицательными")
        return self


class SquareResult(BaseModel):
    """Квадрат одного числа и фактическое время расчёта."""

    number: float
    square: float
    delay: float
    time: float


class CalculateResponse(BaseModel):
    """Результаты, общее время и сравнение с последовательным расчётом."""

    results: list[SquareResult]
    total_time: float
    parallel_faster_than_sequential: bool


async def square_number(number: float, delay: float) -> SquareResult:
    """Подождать заданную паузу и вернуть квадрат числа."""
    # Засекаем фактическое время ожидания, а не запрошенную задержку.
    started = time.perf_counter()
    await asyncio.sleep(delay)
    elapsed = time.perf_counter() - started
    return SquareResult(
        number=number,
        square=number**2,
        delay=delay,
        time=round(elapsed, 2),
    )


@app.post("/calculate/", response_model=CalculateResponse)
async def calculate(payload: CalculateRequest) -> CalculateResponse:
    """Посчитать квадраты параллельно и сравнить время с суммой задержек."""
    started = time.perf_counter()
    results = await asyncio.gather(
        *(
            square_number(number, delay)
            for number, delay in zip(payload.numbers, payload.delays)
        )
    )
    total_time = time.perf_counter() - started

    # Последовательно те же паузы заняли бы сумму задержек.
    sequential_time = sum(payload.delays)
    return CalculateResponse(
        results=list(results),
        total_time=round(total_time, 2),
        parallel_faster_than_sequential=total_time < sequential_time,
    )
