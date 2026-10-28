# AI-first application workflow — implementation and verified limits (2026-10-28)

Live: https://global-work-mesh.pages.dev/

## Workflow shipped

1. Existing collection runs on Windows Task Scheduler `RevenueAgent-Global-Discovery` every six hours, no foreground Chrome focus.
2. `app/revenue_policy.py` separates actual buyer-issued digital-deliverable work from public remote *employment* feeds. Himalayas, Jobicy, Remotive, Arbeitnow and Remoshift are **not** implicitly freelance buyers.
3. `app/auto_application_queue.py` saves potential real marketplace gigs in the private `application-intents.db` SQLite file, unique by provider+URL, with immutable audit events and a non-sent proposal outline. Each run reconciles/rejects false-positive jobs without deleting audit evidence.
4. `scripts/revenue_background.py` invokes `prepare` after each collection, then persists a summary to private Drive. No worker search until an actual awarded and funded contract, client consent, platform permission, and failed AI-only fulfillment.
5. `scripts/global_work_mesh.py` publishes only *aggregate* queue counts to public `jobs.json` (no client/user/worker details or proposals), and the public Pages UI offers:
   - "AI候補の応募を一括開始": hands at most five *AI candidates* to the authenticated ChatGPT workflow.
   - "AIで応募可否を確認": for other displayed listings, begins eligibility screening using the provider's canonical listing URL.
   - "掲載元で応募": external canonical application URL with attribution.
6. On the site, click-through to ChatGPT creates a conversational **request to apply**, not a completed application. The receiving agent still needs its own connected provider's permission and must satisfy required native confirmation. It must report provider-native receipt identifiers as the only proof of actual submission. The public site never contains OAuth tokens or client-account credentials.

## Live run and anti-false-positive fix

Initial queue captured two Himalayas roles (Media Performance Analyst and Brazil B2B Marketing Manager) as AI-first based on incidental digital keywords. Both were employment, not buyer-issued service orders. After root-cause fix, both are `rejected` with audit events; active queue is 0. Public 50 job listings remain available for *employment search*, but AI-service-autoapply count is accurately 0.

Upwork official MCP discovered and prepared a real fixed-price digital project:

- University website structured data extraction, numeric ID `2114645380420484089`, **$250**, 11 Connects of 12 available, ACTIVE / can apply / not yet applied at verification.
- Proposal preview includes complete cover letter, less-than-one-month delivery, by-project payment, no attachments, no certificate/portfolio/work-history entries, no boost (balance too low).
- State: **native Upwork preview only**, NOT submitted. Official MCP requires the user to review the full preview and explicitly confirm the transaction, acknowledge the fixed-price dispute assistance terms, and decide whether to attach files. A broad "auto apply everything" request cannot substitute for the platform's native per-proposal confirmation.
- Never spend Connects or mark a proposal submitted without a successful Upwork receipt. Previously inspected Australian POD sock research also has an Upwork draft preview but no submission.

## Authorization, policy, and hard limits

- Public job-board API keys are read-only and do not confer any right to submit the user's applications.
- Upwork official MCP provides proposal submission **after** a specific preview and confirmation; official Upwork help explicitly requires this. https://support.upwork.com/hc/en-us/articles/55446516654611-How-to-use-Upwork-with-AI-agents-through-MCP
- Freelancer.com terms section 33 prohibits automated website or API interaction without express written permission. https://www.freelancer.com/about/terms
- A web browser login does not become an OAuth API token for a scheduled server.
- No authorized `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `FREELANCER_OAUTH_TOKEN`, or `UPWORK_API_KEY` is configured in the scheduled Windows process environment at verification. The persistent worker therefore uses deterministic, truthful proposal scaffolds rather than claiming unmonitored LLM API generation.
- Never use browser cookies, unattended mass bidding, hidden third-party IP, login bypass, paid account purchases or manufactured successes.
- Public website must never expose a direct POST route that submits under the owner's identity without per-user authentication and provider write permissions. This is why its application button opens the user's own authenticated workflow.

## Verification

```sh
python -m pytest -q
python -m app.auto_application_queue --root "<private synced Drive folder>"
node --check web/global-work-mesh/app.js
python scripts/global_work_mesh.py --root "<private synced Drive folder>" --deploy
```

Tests: 68 passed, 1 non-fatal Starlette/httpx warning. Production Cloudflare deployment returned exit code 0, public URL and JSON returned HTTP 200. Confirmed submitted proposals: **0**; awards: **0**; paid revenue: **0**.

### Remaining work

An actual automated native-proposal submission requires a provider-authorized write adapter with verified permitted scope, canonical job identity, rate/Connects ceilings, safe retry, data access rights, and a receipt reconciler. Many platforms additionally require the user to confirm each final proposal. The UI should only display actual submissions after this reconciliation.
