from pydantic import BaseModel


# Request Bodies
class CreateRequestBody(BaseModel):
    user_id: int


# Responses
class UserResponse(BaseModel):
    id: int


class RequestResponse(BaseModel):
    user_id: int
    remaining: int
    resets_in_seconds: float


class QuotaResponse(BaseModel):
    user_id: int
    max_requests: int
    used: int
    remaining: int
    resets_in_seconds: float
