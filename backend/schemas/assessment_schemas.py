from pydantic import BaseModel, Field


class SubmitResponseSchema(BaseModel):
    text_data: str = Field(min_length=1)
    clipboard_detected: bool = False
