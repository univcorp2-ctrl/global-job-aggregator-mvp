from __future__ import annotations

from contextlib import asynccontextmanager
from html import escape
import hmac
import os
from pathlib import Path

from fastapi import Header
from pydantic import BaseModel, Field
from app.workers import connect_workers, register_worker, search_workers, match_workers, prepare_contact, provider_capabilities
from app.supply_connectors import freelancer_search

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core import Settings, collect_all, connect, get_job, init_db, list_jobs, source_counts

load_dotenv()
settings = Settings.from_env()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(settings.db_path)
    yield


app = FastAPI(title="Global Job Aggregator MVP", version="1.0.0", lifespan=lifespan)

STYLE = """
<style>
body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;background:#f6f8fb;color:#111827}
.top{background:#0f172a;color:white;padding:16px 24px}.top a{color:white;font-weight:800;text-decoration:none}
.wrap{width:min(1180px,94vw);margin:28px auto}.hero,.card,.detail{background:white;border:1px solid #e5e7eb;border-radius:22px;padding:20px;box-shadow:0 10px 30px rgba(15,23,42,.05)}
.hero{display:flex;justify-content:space-between;gap:16px;align-items:center;background:linear-gradient(135deg,#fff,#eef4ff)}
h1{margin:0 0 8px;font-size:clamp(28px,4vw,44px)}p{color:#6b7280;line-height:1.6}
button{border:0;border-radius:14px;background:#2563eb;color:white;font-weight:700;padding:12px 16px;cursor:pointer}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:16px 0}.card span{display:block;color:#6b7280;margin-top:4px}
.filters{display:grid;grid-template-columns:2fr 1fr 1fr .6fr auto;gap:10px;margin:16px 0}input,select{border:1px solid #e5e7eb;border-radius:12px;padding:10px;background:white}
.table{overflow-x:auto;background:white;border:1px solid #e5e7eb;border-radius:18px}table{width:100%;border-collapse:collapse;min-width:980px}th,td{padding:12px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}
th{color:#6b7280;font-size:12px;text-transform:uppercase}.p{display:inline-flex;min-width:28px;justify-content:center;border-radius:999px;padding:4px 8px;font-weight:800}.pA{background:#dcfce7;color:#166534}.pB{background:#fef9c3;color:#854d0e}.pC{background:#e5e7eb;color:#374151}a{color:#2563eb;text-decoration:none}.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.meta div{border:1px solid #e5e7eb;border-radius:14px;padding:12px}.draft,.desc{background:#f6f8fb;border-radius:14px;padding:14px;white-space:pre-wrap;color:#111827}
@media(max-width:760px){.hero{flex-direction:column;align-items:stretch}.filters{grid-template-columns:1fr}}
</style>
"""


def layout(title: str, body: str) -> str:
    safe_title = escape(title)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{safe_title}</title>{STYLE}</head><body>"
        "<header class='top'><a href='/'>Global Job Aggregator</a> "
        "<span>Safety-first MVP</span></header>"
        f"<main class='wrap'>{body}</main></body></html>"
    )


def text(value: object, default: str = "-") -> str:
    if value is None or value == "":
        return default
    return escape(str(value))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "db_path": str(settings.db_path)}


@app.get("/", response_class=HTMLResponse)
def index(
    q: str | None = None,
    source: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> str:
    with connect(settings.db_path) as conn:
        jobs = list_jobs(conn, q=q, source=source, status=status, priority=priority, limit=limit)
        counts = source_counts(conn)

    cards = "".join(
        f"<div class='card'><strong>{text(c['source'])}</strong><span>{c['count']} jobs</span></div>"
        for c in counts
    ) or "<div class='card'><strong>No jobs yet</strong><span>Run collection to populate SQLite.</span></div>"

    rows = []
    for job in jobs:
        rows.append(
            "<tr>"
            f"<td><span class='p p{text(job['application_priority'])}'>{text(job['application_priority'])}</span></td>"
            f"<td>{job['ai_relevance']:.0f}</td>"
            f"<td><a href='/jobs/{job['id']}'>{text(job['title'])}</a></td>"
            f"<td>{text(job['company'])}</td><td>{text(job['source'])}</td>"
            f"<td>{text(job['remote'], 'unknown')}</td><td>{text(job['japan_ok'], 'unknown')}</td>"
            f"<td>{text(job['compensation'] or job['expected_monthly_income'])}</td>"
            f"<td>{text(job['status'])}</td></tr>"
        )
    table_rows = "".join(rows) or "<tr><td colspan='9'>No matching jobs.</td></tr>"
    body = f"""
    <section class='hero'>
      <div><h1>Aggregated opportunities</h1><p>Official/public API-first job collection with AI relevance, fit score, and proposal drafts.</p></div>
      <form method='post' action='/collect'><button type='submit'>Run collection now</button></form>
    </section>
    <section class='cards'>{cards}</section>
    <form class='filters' method='get'>
      <input name='q' placeholder='Search keyword' value='{text(q, '')}'>
      <input name='source' placeholder='source' value='{text(source, '')}'>
      <select name='priority'><option value=''>Any priority</option><option value='A'>A</option><option value='B'>B</option><option value='C'>C</option></select>
      <input name='limit' type='number' min='1' max='500' value='{limit}'><button>Filter</button>
    </form>
    <div class='table'><table><thead><tr><th>Priority</th><th>Score</th><th>Title</th><th>Company</th><th>Source</th><th>Remote</th><th>Japan</th><th>Compensation</th><th>Status</th></tr></thead><tbody>{table_rows}</tbody></table></div>
    """
    return layout("Jobs", body)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(job_id: int) -> str:
    with connect(settings.db_path) as conn:
        job = get_job(conn, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    skills = ", ".join(job.get("required_skills") or [])
    url = f"<a href='{text(job['url'], '#')}' target='_blank' rel='noopener'>Open source</a>" if job.get("url") else "-"
    body = f"""
    <p><a href='/'>← Back</a></p><article class='detail'>
    <div style='display:flex;justify-content:space-between;gap:12px;align-items:start'>
      <div><h1>{text(job['title'])}</h1><p>{text(job['company'], 'Unknown company')} · {text(job['source'])}</p></div>
      <span class='p p{text(job['application_priority'])}'>{text(job['application_priority'])}</span>
    </div>
    <dl class='meta'><div><dt>URL</dt><dd>{url}</dd></div><div><dt>Location</dt><dd>{text(job['location'])}</dd></div><div><dt>Remote</dt><dd>{text(job['remote'], 'unknown')}</dd></div><div><dt>Japan OK</dt><dd>{text(job['japan_ok'], 'unknown')}</dd></div><div><dt>Compensation</dt><dd>{text(job['compensation'] or job['expected_monthly_income'])}</dd></div><div><dt>AI relevance</dt><dd>{job['ai_relevance']:.0f}</dd></div><div><dt>Fit score</dt><dd>{job['fit_score']:.0f}</dd></div><div><dt>Skills</dt><dd>{text(skills)}</dd></div></dl>
    <h2>Proposal draft</h2><p class='draft'>{text(job['proposal_draft'])}</p><h2>Description</h2><p class='desc'>{text(job['description'], 'No description stored.')}</p></article>
    """
    return layout(str(job["title"]), body)


@app.get("/api/jobs")
def api_jobs(
    q: str | None = None,
    source: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, object]:
    with connect(settings.db_path) as conn:
        return {"jobs": list_jobs(conn, q=q, source=source, status=status, priority=priority, limit=limit)}


@app.get("/api/jobs/{job_id}")
def api_job_detail(job_id: int) -> dict[str, object]:
    with connect(settings.db_path) as conn:
        job = get_job(conn, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/collect")
async def api_collect(force: bool = False) -> dict[str, object]:
    summary = await collect_all(settings=settings, force=force)
    return summary.as_dict()


@app.post("/collect")
async def collect_from_dashboard():
    await collect_all(settings=settings, force=True)
    return RedirectResponse(url="/", status_code=303)


# Worker/supplier information is not public. This router fails closed without
# WORKER_DB_TOKEN. The public jobs dashboard cannot access personal profiles.
WORKERS_DB_PATH = Path(os.environ.get("WORKERS_DB_PATH", "data/workers-private.db"))


def _require_worker_token(value: str | None) -> None:
    expected = os.environ.get("WORKER_DB_TOKEN", "")
    if not expected or not value or not hmac.compare_digest(expected, value):
        raise HTTPException(status_code=401, detail="Private supply API: credential required")


class WorkerRegistration(BaseModel):
    platform: str
    external_id: str = Field(min_length=1, max_length=130)
    display_label: str = Field(min_length=1, max_length=120)
    skills: list[str] = Field(min_length=1, max_length=30)
    profile_url: str | None = None
    location: str | None = None
    languages: list[str] = Field(default_factory=list)
    remote_ok: bool = False
    hourly_rate: float | None = None
    currency: str | None = None
    availability: str = "unknown"
    worker_opted_in: bool = False


class ContactDraftRequest(BaseModel):
    job_id: int = Field(gt=0)
    worker_id: str


@app.get("/api/supply/providers")
def api_supply_providers(x_worker_token: str | None = Header(default=None)):
    _require_worker_token(x_worker_token)
    return {"providers": provider_capabilities(), "note": "Capability matrix, not authenticated live sessions."}


@app.post("/api/workers")
def api_register_opted_in_worker(payload: WorkerRegistration,
                                 x_worker_token: str | None = Header(default=None)):
    _require_worker_token(x_worker_token)
    if not payload.worker_opted_in:
        raise HTTPException(status_code=422, detail="Explicit worker consent is required")
    try:
        with connect_workers(WORKERS_DB_PATH) as db:
            worker_id = register_worker(
                db, platform=payload.platform, external_id=payload.external_id,
                display_label=payload.display_label, skills=payload.skills,
                profile_url=payload.profile_url, languages=payload.languages,
                location=payload.location, remote_ok=payload.remote_ok,
                hourly_rate=payload.hourly_rate, currency=payload.currency,
                availability=payload.availability,
                consent_basis="opt_in", profile_origin="worker_submission",
            )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"id": worker_id, "registered": True, "contact_authorized": False}


@app.get("/api/workers")
def api_workers(skill: str = "", platform: str = "", limit: int = Query(default=50, ge=1, le=100),
                x_worker_token: str | None = Header(default=None)):
    _require_worker_token(x_worker_token)
    with connect_workers(WORKERS_DB_PATH) as db:
        items = search_workers(db, skill=skill, platform=platform, limit=limit)
    return {"count": len(items), "workers": items}


@app.get("/api/workers/discover/freelancer")
async def api_discover_freelancer(q: str = "python",
                                  limit: int = Query(default=10, ge=1, le=10),
                                  x_worker_token: str | None = Header(default=None)):
    _require_worker_token(x_worker_token)
    try:
        return await freelancer_search(query=q, limit=limit)
    except (ValueError, Exception) as error:
        if isinstance(error, ValueError):
            raise HTTPException(status_code=422, detail=str(error)) from error
        # Never surface provider responses, OAuth secrets or private tokens.
        raise HTTPException(status_code=502, detail="Provider request failed") from error


@app.get("/api/matches/{job_id}")
def api_match_workers(job_id: int, limit: int = Query(default=10, ge=1, le=50),
                      x_worker_token: str | None = Header(default=None)):
    _require_worker_token(x_worker_token)
    with connect(settings.db_path) as jobs_db:
        job = get_job(jobs_db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    with connect_workers(WORKERS_DB_PATH) as workers_db:
        matches = match_workers(workers_db, job, limit=limit)
    return {"job_id": job_id, "matches": matches,
            "warning": "Unverified subcontracting rights, platform contact permissions, and payability."}


@app.post("/api/workers/contact-draft")
def api_contact_draft(payload: ContactDraftRequest,
                      x_worker_token: str | None = Header(default=None)):
    _require_worker_token(x_worker_token)
    with connect(settings.db_path) as db:
        job = get_job(db, payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    with connect_workers(WORKERS_DB_PATH) as db:
        try:
            draft = prepare_contact(db, job=job, worker_id=payload.worker_id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
    return draft


@app.get("/workers", response_class=HTMLResponse)
def workers_dashboard() -> str:
    # The page includes no server-rendered private worker records. Token stays
    # in a transient in-memory input value and is never persisted or transmitted
    # to an outside host. No contact/send functionality on this page.
    return layout("Worker supply", """
    <section class="hero"><div><h1>Worker supply</h1>
    <p>Private opt-in worker database / skills search. No mass messaging.</p></div>
    </section>
    <div class="card"><p>Enter your private API token for this session.</p>
    <input id="key" type="password" placeholder="WORKER_DB_TOKEN" autocomplete="off">
    <input id="skill" placeholder="Skill keyword, e.g. python">
    <button id="load" type="button">View permitted workers</button>
    <p id="status"></p></div>
    <div id="list" class="cards"></div>
    <script>
    document.getElementById('load').addEventListener('click',async()=>{
       const key=document.getElementById('key').value;
       const skill=document.getElementById('skill').value;
       const out=document.getElementById('list');
       const status=document.getElementById('status');
       out.replaceChildren();
       try {
         const r=await fetch('/api/workers?skill='+encodeURIComponent(skill),{
           headers:{'x-worker-token':key},cache:'no-store'
         });
         if(!r.ok){status.textContent='Unauthorized or service unavailable ('+r.status+')';return;}
         const data=await r.json();
         status.textContent=data.count+' permitted worker profile(s)';
         for (const item of data.workers){
           const card=document.createElement('div');card.className='card';
           const title=document.createElement('strong');
           title.textContent=item.display_label+' / '+item.platform;
           const info=document.createElement('p');
           info.textContent=item.skills.join(', ')+' | '+(item.location||'location unknown');
           card.append(title,info);
           if (item.profile_url) {
             const a=document.createElement('a');a.href=item.profile_url;a.rel='noopener noreferrer';
             a.target='_blank';a.textContent='Original platform profile';
             card.append(a);
           }
           out.append(card);
         }
       }catch(error){status.textContent='Connection failed';}
    });
    </script>
    """)
