"""Admin endpoints for managing courses (stubs — wired up in a later ticket)."""

from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter(prefix="/courses", tags=["courses"])


class CourseCreate(BaseModel):
    name: str


class CourseResponse(BaseModel):
    name: str


@router.post("", status_code=status.HTTP_501_NOT_IMPLEMENTED, response_model=CourseResponse)
async def create_course(payload: CourseCreate) -> CourseResponse:
    """TODO: persist course config (see future ticket)."""
    return CourseResponse(name=payload.name)


@router.delete("/{name}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def delete_course(name: str) -> dict[str, str]:
    """TODO: remove course config (see future ticket)."""
    return {"name": name}
