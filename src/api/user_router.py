from fastapi import APIRouter, Request, HTTPException
from src.services.user_service import register_user
from src.utils.logging_utils import log_structured
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/users", tags=["users"])

class UserRegistrationRequest(BaseModel):
    email: str
    first_name: str
    last_name: str
    company: str

@router.post("/register")
async def register_user_endpoint(request: Request, user_data: UserRegistrationRequest):
    try:
        # Extract IP from request
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0]
        else:
            ip_address = request.client.host
            
        result = register_user(
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            company=user_data.company,
            ip_address=ip_address
        )
        return result
    except Exception as e:
        log_structured("UserRegistrationEndpointError", error=str(e), email=user_data.email)
        raise HTTPException(status_code=500, detail="Internal Server Error")
