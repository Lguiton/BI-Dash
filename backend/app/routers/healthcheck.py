from fastapi import APIRouter
from pydantic import BaseModel

from app.services import health_check

router = APIRouter(prefix="/api/health-check", tags=["health"])


@router.get("")
def check():
    return health_check.run()


class LaptopIn(BaseModel):
    laptop: bool | None = None
    encrypted: bool | None = None
    locks: bool | None = None
    findmy: bool | None = None
    windows_signin: bool | None = None


@router.get("/laptop")
def get_laptop():
    return health_check.laptop()


@router.put("/laptop")
def put_laptop(b: LaptopIn):
    return health_check.set_laptop(b.model_dump(exclude_none=True))
