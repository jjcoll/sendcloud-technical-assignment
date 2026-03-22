from fastapi import FastAPI, HTTPException
from app.store import store
from app.schemas import QuotaResponse, RequestResponse, UserResponse, CreateRequestBody


app = FastAPI()


@app.post("/users", status_code=201, response_model=UserResponse)
def create_user():
    user = store.create_user()
    return {"id": user.id}


@app.post("/requests", status_code=201, response_model=RequestResponse)
def send_request(body: CreateRequestBody):
    user = store.get_user(body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    allowed, resets_in, remaining = store.record_request(user)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(int(resets_in) + 1)},
        )

    return {
        "user_id": user.id,
        "remaining": remaining,
        "resets_in_seconds": round(resets_in, 2),
    }


@app.get("/users/{id}/quota", response_model=QuotaResponse)
def get_user_quota(id: int):
    user = store.get_user(id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    resets_in, remaining_slots = store.get_quota(user)
    return {
        "user_id": user.id,
        "max_requests": 10,
        "used": 10 - remaining_slots,
        "remaining": remaining_slots,
        "resets_in_seconds": round(resets_in, 2),
    }
