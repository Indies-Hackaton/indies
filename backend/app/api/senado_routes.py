"""FastAPI routes for Senate transparency data.

Exposes one endpoint backed by :class:`~app.services.senado_scraper.SenadoClient`.
The client is injected from ``app.state`` (created once at startup) so it reuses
the shared connection pool — no browser, no per-request overhead.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.services.senado_scraper import SenadoClient, SenadoScraperError

router = APIRouter(prefix="/api/v1/senado", tags=["senado"])


def get_senado_client(request: Request) -> SenadoClient:
    """Return the shared :class:`SenadoClient` from application state."""
    return request.app.state.senado_client


@router.get(
    "/support-staff",
    summary="Support-staff salary data from the Senate transparency API",
)
async def get_support_staff(
    year: int = Query(..., description="Fiscal year, e.g. 2024."),
    month: str = Query(..., description="Month in Spanish, e.g. MARZO."),
    senator: str | None = Query(None, description="Partial senator name filter."),
    support_staff: str | None = Query(None, description="Partial staff name filter."),
    senado: SenadoClient = Depends(get_senado_client),
) -> dict[str, Any]:
    """Return support-staff salary records for the requested period.

    Calls the Senate REST API (no browser), handles pagination automatically,
    and applies optional accent-insensitive substring filters.
    """
    try:
        df = await senado.scrape_support_staff(
            year=year,
            month=month,
            senator=senator,
            support_staff=support_staff,
        )
    except SenadoScraperError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "year": year,
        "month": month.upper(),
        "total_records": len(df),
        "records": df.to_dict(orient="records"),
    }
