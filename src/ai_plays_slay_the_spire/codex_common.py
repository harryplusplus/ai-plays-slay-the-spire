from typing import Self

from pydantic import BaseModel, model_validator


class CodexRequestId:
    def __init__(self) -> None:
        self._id = 0

    def next(self) -> int:
        id = self._id
        self._id += 1
        return id


class CodexError(BaseModel):
    code: int
    message: str


class CodexResponse(BaseModel):
    id: int
    error: CodexError | None = None
    result: dict | None = None

    @model_validator(mode="after")
    def check_result_or_error(self) -> Self:
        if (self.result is not None and self.error is not None) or (
            self.result is None and self.error is None
        ):
            raise ValueError("Exactly one of result or error must be provided")
        return self

    def is_result(self) -> bool:
        return self.result is not None
