"""Read-only platform discovery. No credential fallback, scraping, or DMs."""
from __future__ import annotations

import os
from urllib.parse import quote

import httpx

API = "https://www.freelancer.com/api/users/0.1/users/directory/"

async def freelancer_search(*, query: str, limit: int = 10, token: str | None = None,
                            client: httpx.AsyncClient | None = None) -> dict:
    """Use only the official Freelancer OAuth 0.1 users/directory endpoint.

    The result is an ephemeral preview, NOT a data resale feed or contact list.
    User emails, phones, and other private fields are discarded.
    """
    if not query.strip() or len(query.strip()) > 80:
        raise ValueError("Search query must be 1 to 80 characters")
    secret = token or os.environ.get("FREELANCER_OAUTH_TOKEN")
    if not secret:
        return {"connected": False, "provider": "freelancer",
                "profiles": [], "blocked_reason": "official_oauth_token_required"}
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=15, follow_redirects=False)
    try:
        response = await client.get(
            API,
            params={"query": query.strip(), "limit": max(1, min(limit, 10)),
                    "offset": 0, "compact": "true"},
            headers={"Freelancer-OAuth-V1": secret,
                     "User-Agent": "GlobalJobAggregatorMVP/worker-discovery"},
        )
        if response.status_code in (401, 403):
            return {"connected": False, "provider": "freelancer",
                    "profiles": [], "blocked_reason": "oauth_permission_denied"}
        response.raise_for_status()
        payload = response.json()
        raw = payload.get("result", payload)
        if isinstance(raw, dict):
            records = raw.get("users") or raw.get("freelancers") or []
        elif isinstance(raw, list):
            records = raw
        else:
            records = []
        result = []
        for item in records[:10]:
            if not isinstance(item, dict):
                continue
            username = str(item.get("username") or "").strip()
            if not username or not username.replace("_", "").replace("-", "").isalnum():
                continue
            offers = item.get("skills") or item.get("job_skills") or []
            skills = sorted(set(x.lower() for x in offers if isinstance(x, str) and len(x) < 50))
            result.append({
                "provider": "freelancer",
                "profile_url": f"https://www.freelancer.com/u/{quote(username)}",
                "display_label": str(item.get("display_name") or username)[:120],
                "skills": skills[:20], "skills_verified": False,
                "rate": item.get("hourly_rate") if isinstance(item.get("hourly_rate"), (int,float)) else None,
                "contact_state": "not_authorized_no_message_sent",
            })
        return {"connected": True, "provider": "freelancer", "profiles": result,
                "count": len(result), "may_persist": False,
                "note": "Live preview only. Official project-scoped messaging requires separate context."}
    finally:
        if own_client:
            await client.aclose()
