# Worker supply / cross-platform delegation MVP (2026-10-27)

## Goal and honesty gates

Find legitimate client-side job opportunities, find workers who voluntarily want to perform work, score the skill match, and prepare a **platform-native inquiry** for review. An inbound job listing is **not** automatically a subcontractable engagement. No real outreach, contract, payment, or person-data bulk import has happened.

Existing demand collector `scripts/collect_once.py -> app.core.collect_all` continues collecting five open job APIs. New `app/workers.py` is **independent private SQLite**. `app/supply_connectors.py` has an optional authenticated Freelancer.com search-preview connector, never a mass-contacts harvesting tool.

## Official provider decision matrix

| Provider | Location | Official supply search | Contact via API/MCP | Present credentials | Automated status |
| --- | --- | --- | --- | --- | --- |
| Contra | global | MCP talent by skills, role, location | Native in-platform inquiry/project proposal with prepare/confirm | Not connected; profile onboarding unfinished | Connector research only |
| Freelancer.com | global | OAuth users/directory search, rate/skills/profile via official SDK | Project-scoped message threads if account and project permissions allow | OAuth token not connected | API read-only preview implemented; returns BLOCKED if absent |
| Coconala (ココナラ) | Japan | Official MCP service search/recommendation | Checkout and purchase remain on Coconala; no general contact/send MCP confirmed | No connected Coconala integration in this agent | Query via first-party client after connection; not mass imported |
| CrowdWorks | Japan | No verified public worker-directory API | Site-only; no external deal-brokering | None | Manual partner permission required |
| Lancers | Japan | No verified public worker-directory API | Site-only (no verified messaging API) | None | Manual partner permission required |
| Wantedly Hire | Japan | Employer ATS MCP sees *your own* candidates | Current MCP read-only | No employer data credentials | Wrong fit for public freelancers |
| Get on Board | LATAM/global | Employer OAuth MCP search_talent + talent_profile | Requires company/permissions/unlock, no general bulk-message permission verified | No employer OAuth | Partner/enterprise path |
| Self-referred contractor | Japan/global | Direct worker-submitted skills/portfolio under consent | Contact only after consent and reviewer approval | No real submissions yet | Owner-authenticated intake API implemented |

Sources: https://contra.com/features/mcp,
https://github.com/freelancer/freelancer-sdk-python,
https://mcp.ai-assist.coconala.com/legal/mcp_terms,
https://www.coconala.co.jp/news-20260805/,
https://crowdworks.jp/pages/agreement,
https://hire.wantedly.com/mcp,
https://www.getonbrd.com/help/what-is-the-getonbrd-mcp-server.
Check version and current terms before production.

## Security and privacy

- Set environment variable `WORKER_DB_TOKEN` to a strong secret **outside git**. Endpoints always return HTTP 401 if missing or wrong.
- Set optional `WORKERS_DB_PATH` to a private local or encrypted disk, never public static web artifacts or CI artifacts.
- Allow only worker-consented profiles to be stored with the authenticated admin intake. The current code verifies the *declared* opt-in flag; the operator must independently retain consent evidence.
- For external talent marketplaces, discovery API previews are intentionally ephemeral. No bulk persistence/retargeting unless the marketplace grants it.
- Store only platform, self-submitted label, skills, work location, consent basis, languages, remote availability, currency/rate, official profile URL, TTL. **No phone/email, age, gender, protected traits, or profiles from scraping**.
- `platform_authorized` records expire after 30 days. Self-registered consent records expire after 365 days without refresh.
- No cross-platform direct messaging without rights and consent. Respect non-circumvention and platform fee agreements; work contracted on site A must be subcontractable before using workers from site B.
- **No actual message-sending routes are exposed**. `contact-draft` creates a local proposed text and returns `send_enabled=false`. Never present "prepared" as "sent".

## Run locally

```powershell
# Choose a strong locally-held WORKER_DB_TOKEN before starting.
$env:WORKER_DB_TOKEN = "<set-outside-repository>"
$env:WORKERS_DB_PATH = "data/workers-private.db"
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8798
```

In a browser on that computer open `http://127.0.0.1:8798/workers`, enter the secret transiently, and search for skills. No production cloud hosting, external URLs, or public data sharing have yet been activated.

### Private endpoints

- `GET /api/supply/providers`: capability matrix with real `connected=false` flags.
- `GET /api/workers?skill=python&platform=opt_in`: only unexpired consent/authorized records.
- `POST /api/workers`: authenticated consented worker intake, `worker_opted_in:true` (must be verified outside system).
- `GET /api/workers/discover/freelancer?q=python`: official user directory preview with optional `FREELANCER_OAUTH_TOKEN` in server env. Without token responds `connected:false`, never fabricates workers.
- `GET /api/matches/{job_id}`: rank only candidates who share skills with a collected job. Every result marked `subcontract_permission_unverified`.
- `POST /api/workers/contact-draft`: authenticated draft creation, no dispatch, even with OAuth credentials.

Set header `x-worker-token: <secret>` on API calls. UI page contains no embedded personal data and fetches only authenticated results. Do not paste secrets into issue/CI logs.

## Validation and next action

1. Twelve offline tests (existing public-connector tests + worker tests) passed on the user's Windows machine after resolving SQLite handles not closing. 1 non-blocking FastAPI/httpx version deprecation warning.
2. Live OAuth worker search on Freelancer **not yet executed**; provider token/permission remains blocked. Search preview is tested with an HTTP mock and output fields scrubbed.
3. No real worker profiles imported at 2026-10-27. Database is intentionally empty, not populated with fictional workers.
4. Cross-platform delegation is a **policy-gated hypothesis**, not a proven way to resell every job. For each proposed match verify: original client's explicit subcontract permission, worker consent, client data disclosure approval, confidentiality, scope, payment/fees, and no direct-deal circumvention.
5. Next: finish Contra employer onboarding/OAuth and ask for first-party allowed talent search; obtain Freelancer OAuth2 portal permission; query Japanese Coconala via official first-party MCP UI, not cloned profile scraping; onboard 3 consenting workers; obtain 1 real fixed-scope job that expressly allows subcontractors. Only after human review send **one** platform-native invite and verify receipt (not in the current implementation).
