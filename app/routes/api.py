from urllib.parse import urljoin
from fastapi import APIRouter, Request, Response

from app.core.settings import settings
from app.core.limiter import limiter
from app.routes import webhook


router = APIRouter(prefix=settings.API_PREFIX)


@router.get("/", response_model=dict[str, str], tags=["root"])
@limiter.limit("10/minute")
def info(request: Request, response: Response) -> dict[str, str]:
    return {
        "title": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "docs_url": urljoin(str(settings.API_URL), "/docs"),
    }


@router.get("/health", tags=["root"])
@limiter.limit("10/minute")
def health_check(request: Request, response: Response) -> dict[str, str]:
    return {"status": "ok"}


router.include_router(webhook.router)
