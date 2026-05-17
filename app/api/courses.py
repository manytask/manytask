"""Admin endpoints for managing courses."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ValidationError

from app.api.auth import (
    verify_admin_token,
    verify_course_or_admin_token,
    verify_course_token,
)
from app.api.dependencies import get_course_store
from app.models import load_manytask_yaml
from app.storage import CourseStore

router = APIRouter(prefix="/courses", tags=["courses"])


class CourseSummary(BaseModel):
    name: str
    schema_version: int
    tasks_count: int
    updated_at: str | None = None


class CourseListItem(CourseSummary):
    pass


@router.post(
    "/{name}",
    status_code=status.HTTP_201_CREATED,
    response_model=CourseSummary,
)
async def upsert_course(
    name: str,
    request: Request,
    course_token: str = Depends(verify_course_token),  # noqa: B008
    store: CourseStore = Depends(get_course_store),  # noqa: B008
) -> CourseSummary:
    raw_body = await request.body()
    yaml_text = raw_body.decode("utf-8", errors="replace")

    try:
        config = load_manytask_yaml(yaml_text)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid manytask.yml", "message": str(err)},
        ) from None
    except ValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid mr_review section", "errors": err.errors()},
        ) from None

    await store.upsert_course(name, config, course_token=course_token)

    return CourseSummary(
        name=name,
        schema_version=config.schema_version,
        tasks_count=len(config.tasks),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.delete(
    "/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_course(
    name: str,
    _token: str = Depends(verify_course_or_admin_token),  # noqa: B008
    store: CourseStore = Depends(get_course_store),  # noqa: B008
) -> None:
    await store.delete_course(name)


@router.get(
    "",
    response_model=list[CourseListItem],
    dependencies=[Depends(verify_admin_token)],
)
async def list_courses(
    store: CourseStore = Depends(get_course_store),  # noqa: B008
) -> list[CourseListItem]:
    items: list[CourseListItem] = []
    for name in await store.list_courses():
        loaded = await store.get_course(name)
        if loaded is None:
            items.append(
                CourseListItem(
                    name=name,
                    schema_version=-1,
                    tasks_count=0,
                    updated_at=None,
                )
            )
            continue
        _, cfg, _ = loaded
        items.append(
            CourseListItem(
                name=name,
                schema_version=cfg.schema_version,
                tasks_count=len(cfg.tasks),
                updated_at=None,
            )
        )
    return items
