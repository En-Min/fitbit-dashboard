"""
Fitbit OAuth2 authentication router.

Handles the Authorization Code Grant Flow:
  1. /api/auth/fitbit     — redirect user to Fitbit consent screen
  2. /api/auth/callback   — exchange code for tokens, persist in DB
  3. /api/auth/status      — check whether valid (non-expired) tokens exist
  4. /api/sync             — trigger a full incremental sync
"""

import time
import urllib.parse

import httpx
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import OAuthToken

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCOPES = (
    "activity heartrate sleep profile weight "
    "oxygen_saturation respiratory_rate temperature"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_stored_token(db: Session) -> OAuthToken | None:
    """Return the most recent OAuth token row, if any."""
    return (
        db.query(OAuthToken)
        .order_by(OAuthToken.id.desc())
        .first()
    )


async def refresh_access_token(db: Session) -> OAuthToken:
    """Use the stored refresh_token to obtain a new access_token.

    Updates the row in-place and returns it.  Raises HTTPException if no
    token exists or the refresh call fails.
    """
    token = _get_stored_token(db)
    if token is None:
        raise HTTPException(status_code=401, detail="No OAuth token stored. Please authenticate first.")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.FITBIT_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": token.refresh_token,
                "client_id": settings.FITBIT_CLIENT_ID,
            },
            auth=(settings.FITBIT_CLIENT_ID, settings.FITBIT_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail=f"Token refresh failed ({response.status_code}): {response.text}",
        )

    data = response.json()
    token.access_token = data["access_token"]
    token.refresh_token = data["refresh_token"]
    token.expires_at = time.time() + data.get("expires_in", 28800)
    token.token_type = data.get("token_type", "Bearer")
    token.scope = data.get("scope", "")
    token.user_id = data.get("user_id", token.user_id)
    db.commit()
    db.refresh(token)
    return token


async def get_valid_token(db: Session) -> OAuthToken:
    """Return a valid (non-expired) token, refreshing automatically if needed."""
    token = _get_stored_token(db)
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated. Please connect your Fitbit account.")

    # Refresh 60 seconds before actual expiry to avoid edge-case failures
    if time.time() >= (token.expires_at - 60):
        token = await refresh_access_token(db)

    return token


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/auth/fitbit")
async def fitbit_authorize():
    """Redirect the user to Fitbit's OAuth2 authorization page."""
    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": settings.FITBIT_CLIENT_ID,
        "redirect_uri": settings.FITBIT_REDIRECT_URI,
        "scope": SCOPES,
    })
    return RedirectResponse(url=f"{settings.FITBIT_AUTH_URL}?{params}")


@router.get("/auth/callback")
async def fitbit_callback(code: str, db: Session = Depends(get_db)):
    """Exchange the authorization code for an access + refresh token pair.

    Stores the tokens in the OAuthToken table, then redirects the user back
    to the frontend.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.FITBIT_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.FITBIT_REDIRECT_URI,
                "client_id": settings.FITBIT_CLIENT_ID,
            },
            auth=(settings.FITBIT_CLIENT_ID, settings.FITBIT_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Token exchange failed ({response.status_code}): {response.text}",
        )

    data = response.json()

    # Upsert: remove any previous token rows so we keep exactly one
    db.query(OAuthToken).delete()

    token = OAuthToken(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        token_type=data.get("token_type", "Bearer"),
        expires_at=time.time() + data.get("expires_in", 28800),
        scope=data.get("scope", ""),
        user_id=data.get("user_id"),
    )
    db.add(token)
    db.commit()

    # Redirect the user back to the frontend after successful auth
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/?auth=success")


@router.get("/auth/status")
async def auth_status(db: Session = Depends(get_db)):
    """Check whether we currently hold a valid Fitbit token."""
    token = _get_stored_token(db)
    if token is None:
        return {
            "authenticated": False,
            "user_id": None,
            "expires_at": None,
        }

    is_expired = time.time() >= token.expires_at
    return {
        "authenticated": not is_expired,
        "user_id": token.user_id,
        "expires_at": token.expires_at,
        "token_type": token.token_type,
        "scope": token.scope,
    }


@router.post("/sync")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Trigger a full incremental sync of all Fitbit data types.

    The sync runs in a background task so the HTTP request returns quickly.
    """
    # Validate that we have a usable token before queueing work
    await get_valid_token(db)

    # Import here to avoid circular imports at module level
    from app.services.fitbit_sync import run_sync_background

    background_tasks.add_task(run_sync_background)
    return {"status": "sync_started", "message": "Incremental sync has been queued."}
