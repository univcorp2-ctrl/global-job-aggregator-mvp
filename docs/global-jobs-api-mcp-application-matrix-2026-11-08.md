# Worldwide jobs and freelance application API/MCP matrix — 2026-11-08 JST

## Scope and ground truth

Research worldwide (Japan, APAC, South Asia, Europe/UK, Americas, Africa), **separating job listing retrieval from writing a real external application**. This is a dated source-backed reconnaissance note; not a verified assertion that every provider on the existing 108-service Notion registry has a supported API or is currently accepting Japanese residents.

- User objective: discover → qualify → create truthful proposal/sample → **authorized submit** → read back submission ID/status → follow up → contract/deliver/collect.
- Existing code: this repository's daily production path (`scripts/collect_once.py -> app.core`) collects Himalayas, Jobicy, Arbeitnow, Remotive, Remoshift. It persists and scores jobs; drafts are **not submitted**.
- Existing separate orchestration: [Agent_Orchestration/ops/order-hunter](https://github.com/univcorp2-ctrl/Agent_Orchestration/tree/main/ops/order-hunter); its Notion status as of Nov 8 says source queue snapshot last updated Nov 6, latest workflow run not independently verified.
- **Live tested 2026-11-08:** the connected official Upwork MCP successfully authenticated a Freelancer account and searched 5 title queries (Automation, Japanese, Web Research, Data Entry, Python) with 5 returned jobs each = 25 search rows before deduplication. Submissions **0**. This does not imply 25 eligible/unapplied jobs.
- No Freelancer.com OAuth bid, Applystead submit, or other new platform write action was executed in this investigation.

## Functional classification

| Service / region | Read jobs | Write actual freelancer/jobseeker application | Integration and blockers | Confidence |
|---|---|---|---|---|
| **Upwork** — global | Yes | **Yes**, via official authenticated MCP with proposal draft/preview and approval; costs Connects | OAuth connected in present ChatGPT; all write actions must honor approval, existing proposals/invitations and current cost | Live read + primary docs |
| **Freelancer.com** — global | Yes | **Yes**, official OAuth2 API `place_project_bid` and Python SDK | OAuth token and membership/bid limits/costs required; no live authenticated bid this run | Primary code verified; write untested |
| **Contra** — global | Account/projects | Can write proposals to customers using official MCP, **not** validated as general job-board mass application | OAuth and prepare/confirm | Primary docs |
| **Freelance Clearing** — global, emerging | Yes | `submit_bid` via official REST/MCP | OAuth; Stripe Connect payout onboarding; small marketplace/real demand not independently proven | Primary docs only; experimental |
| **Applystead** — global listings | Yes, public MCP | `apply_to_job` via account MCP subject to plan, review and authorisation | Account, membership plan, and external target completion semantics require live confirmation | Primary docs only; experimental |
| **Freelancehunt** — Ukraine/Eastern Europe | Yes, REST | New first-time bid through official API **not verified** | Bearer auth; write for existing proposal/terms is not proof of new bid | Partial |
| **PeoplePerHour** — UK/global | Unofficial Cotlet MCP 17 tools | **No** proposal send in current MCP | Self-hosted/non-commercial or hosted provider; account/session/terms risk | Vendor+repo |
| **Malt** — Europe | Platform UI | No general candidate submission API verified | Regional account, residence/verification needed | Not verified |
| **Worksome / YunoJuno / freelance.de** — Europe | Platform UI | No general candidate submission API verified | Individual eligibility/terms | Not verified |
| **Workana** — LATAM | Platform UI | No general candidate submission API verified | Spanish/Portuguese; residence and payout must be checked per project | Primary site for UI, API not established |
| **Get on Board** — LATAM | Job postings + public API | Recruiter-side MCP is **not** candidate application API | Apply via employer/portal | Primary |
| **Truelancer / Naukri / Zoho Recruit** — India/South Asia | Platform/ATS surfaces | Candidate universal submission API not verified | Regional restrictions; ATS APIs are employer-side | Not verified |
| **CrowdWorks / Lancers / Coconala** — Japan | Public listings/UI | No general approved official candidate bid API verified | Must verify login permissions and individual manual UI operation rules; no bulk unsolicited submission | Not verified |
| **LinkedIn / Indeed** — global | Partner/ATS APIs | Their employer/ATS partner APIs are **not** personal public apply bots | LinkedIn Apply-with-LinkedIn prefill; Indeed Candidate Sync is employer-facing | Primary |
| **Greenhouse / Lever / Ashby / Workable** — global ATS | Public job board GET on participating employer boards | POST is controlled by the recruiting employer's ATS credentials; **not** a public candidate-side key | Use external canonical apply link and approved user interface; no key bypass | Primary |
| **Himalayas** — global | Public REST and 79-tool MCP | **No direct third-party submission** yet, despite 46 authenticated job-seeker tools | Job tracking, résumé/cover letter, apply link; official FAQ expressly says auto-apply on roadmap | Primary, decisive |
| **Jobicy / Remotive / Remoshift** — global | Public API/feed | External apply link only | Attribution/rate limit/data rights | Primary |
| **Arbeitnow** — Germany/EU | Public JSON job board | External apply link only | Company-side UI | Existing connector |
| **Adzuna / Jooble** — multinational | Country/partner job search APIs | External apply link only | API keys, quotas, regional license | Primary/partial |

## Official / primary sources checked

1. https://www.upwork.com/ai/mcp and https://www.upwork.com/developer
2. https://github.com/freelancer/freelancer-sdk-python and https://github.com/freelancer/freelancer-sdk-python/blob/master/examples/place_project_bid.py
3. https://contra.com/features/mcp
4. https://freelanceclearing.com/docs
5. https://applystead.com/developers
6. https://himalayas.app/docs/ai-agents (explicitly says **not directly** apply to jobs)
7. https://github.com/Himalayas-App/himalayas-mcp
8. https://github.com/cotletdev/peopleperhour-api-mcp-server
9. https://apidocs.freelancehunt.com/
10. https://docs.greenhouse.io/job-board
11. https://developers.ashbyhq.com/reference/applicationformsubmit
12. https://docs.indeed.com/api-guides/
13. https://www.getonbrd.com/mcp
14. https://www.workana.com/en/jobs

## Live Upwork search evidence (2026-11-08)

Authentic MCP reads, not an application:
- AI Automation Engineer (Nigeria, $10–60/h; proposals tier 5–10), job ID `2119225186392831956`
- AI Automation Expert n8n/Make (UK, $10–32/h; tier 50+), job ID `2119240627518663813`
- Python Programmer for Automation and Website Development (Pakistan, $10–25/h; tier 5–10), job ID `2119127960127213391`
- Japanese–English Interpreter for Real Estate Contract Negotiations (Canada, $15–40/h; tier 5–10), job ID `2119176085843175826` **requires live human work**, not AI-only delivery
- Web Research and Data Entry: company list of 100 (Indonesia, $10 fixed; tier 20–50; one hire already), job ID `2117594877824619415` **not a priority**

Search results alone do not prove canonical job still open, contractor eligibility from Japan, non-applied status, permission to use AI/subcontract, or net profitability.

## Prioritised integration plan (not yet executed)

1. **Reuse existing Upwork official MCP**: authenticated job search and detailed lookup; check application history/invitations, real Connects balance/cost, location, client history, questions; create preview, human approval, submit once, read back status. Do not expend Connects without confirmation.
2. **Freelancer.com OAuth write adapter**: use its official SDK `place_project_bid` after credentials, terms, limits, idempotency and sandbox test; launch against one approved live project only. Never expose OAuth token in GitHub/Notion.
3. **APAC/Europe/LATAM discovery**: add public, officially documented API adapters (not hidden endpoints) using source attribution, exact canonical job URL, feed quota and per-region eligibility; no platform claiming direct apply without a verified writable endpoint for the candidate account.
4. **Experiment separately** with Applystead and Freelance Clearing only after plan/payments, business quality, acceptance proof, fees and Japanese resident KYC are verified. Do not pay for subscription merely because endpoint exists.

### Hard gates

- Individual job `canonical_id` + employer + current status, jurisdiction/eligibility in Japan, pay method, AI/subcontracting policy, fees, deliverability and margin checked before candidacy.
- Source system **job GET ≠ application POST**, recruitment/employer ATS POST ≠ candidate submission. Himalayas job tracker 'applied' marker ≠ evidence the employer received a proposal.
- Respect platform Terms, anti-spam, CAPTCHA, email contacts and rejected/no-contact lists. No scraping of logged-in pages where prohibited. No duplicate application across accounts or paths.
- External writes require target-specific user approval when provider mandates it; require verified API response + actual provider readback + immutable event id.
- Record stages `discovered -> verified -> approved -> submitted -> viewed -> responded -> hired -> delivered -> paid`; do not conflate.
- Track net expected value per application: `P(win) × (contract price − platform fee − fulfillment cost) − application/connects cost − expected compliance/risk cost`; early-stage unknowns are estimates not results.

## Audit and state

- Technical research: primary documentation and read-only live Upwork tool verified.
- Actual cross-platform OAuth app submission: **NOT DONE**; country/platform write permissions, anti-bot policies and paid costs remain gates.
- Repository change: documentation only; no runtime code, workflow, credentials or external customer data modified.
- Notion reference: https://app.notion.com/p/40610562e58b816e90adfb794a82868d
- Project index: https://app.notion.com/p/3fe10562e58b8112a282e19707783c79
