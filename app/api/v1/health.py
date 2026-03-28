from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def liveness():
    """Always returns 200 — used by load balancers."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(request: Request):
    """
    Readiness check. Verifies Google Sheets connection is available.
    Returns 200 even if Sheets is not configured — warns instead of failing,
    so the app remains usable for local dev/testing.
    """
    sheets = getattr(request.app.state, "sheets", None)
    sheets_ok = sheets.is_available() if sheets else False
    return {
        "status": "ready",
        "sheets_connected": sheets_ok,
        "outreach_graph_ready": getattr(request.app.state, "outreach_graph", None) is not None,
        "telegram_graph_ready": getattr(request.app.state, "telegram_graph", None) is not None,
    }
