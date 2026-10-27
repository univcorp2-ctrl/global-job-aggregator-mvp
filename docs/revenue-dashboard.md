# Revenue Agent Operations — Public progress dashboard

Deployed: https://revenue-agent-ops.pages.dev/

**Goal:** visualize only safe aggregate progress from the autonomous multi-market income scout. This is not a buyer-facing job board, personal-data search interface, or public write API.

## Actual operations (2026-10-27)

- Existing independent Windows Task Scheduler task `RevenueAgent-Global-Discovery` runs `scripts/revenue_background.py` every 6 hours using non-foreground `pythonw.exe`, max 12 minutes. It reads public APIs and writes full logs/SQLite/scan history into the user's **private synced Google Drive** directory.
- Separate task `RevenueAgent-Dashboard-Publish` runs `scripts/revenue_dashboard.py --deploy` every six hours roughly ten minutes after collection (23:38/05:38/11:38/17:38 JST). Hidden/non-foreground `pythonw.exe`, max 5 minutes. Both task definitions are saved in the private Drive folder.
- The publisher strictly builds only five public files: `index.html`, `style.css`, `app.js`, `_headers`, `status.json`. The dashboard source is committed in this repository under `web/revenue-agent/`.
- Cloudflare Pages project `revenue-agent-ops` uses the already authorized local Wrangler OAuth session. Its HTTPS deployment uses `wrangler pages deploy <private Drive>/public-site --project-name revenue-agent-ops --branch main`. Credentials must not be copied into source or logs.
- The public JSON includes whitelisted counters, timestamps, **public source names** (Himalayas/Jobicy/Arbeitnow/Remotive/Remoshift), seven named acceptance gates, and source-by-source success/failure **types only**. No job titles, profiles, identities, URLs, tokens, offers, files, error messages or bank/financial account details are published.
- Browser refresh checks every 5 minutes. Content changes at the six-hour scan+deploy cadence, not every five minutes. State transitions to degraded/offline when a scan becomes stale.
- The production URL, index HTML and `/status.json` were HTTP 200 in an external GET from the PC, and sample counters matched the private 5-source/50-job report.

## Progress denominators

**7 milestones:** successful official API collection; scheduled background collection; candidate ranking/drafting; MCP/Apify discovery; authorized bids submitted; confirmed contracts/subcontracting; verified cash receipt. Milestones 1–4 can be validated without user approval; stages 5–7 remain false until binding provider records and payment confirmations exist. Never convert the public feed's employment listings into fictitious subcontractable gigs.

The dashboard does **not** prove that Upwork/Contra OAuth sessions can be used by scheduled cloud jobs. Account identity checks, bids consuming Connects, approved subcontract orders, and funds movement retain explicit provider-native confirmation. Apify actors must separately pass sales/KYC gates. Current confirmed contract and paid revenue: zero.

## Verification

Run from repository root:

```
python -m pytest -q tests/test_revenue_dashboard.py
python scripts/revenue_dashboard.py --root "<private Google Drive directory>"
node --check web/revenue-agent/app.js
```

Publish (from the authorized local machine only):

```
python scripts/revenue_dashboard.py --root "<private Google Drive directory>" --deploy
```

Check `publish-status.json` for actual exit status, Task Scheduler `LastTaskResult == 0`, and external HTTPS GET responses. A pending commit is not a deployment.

## Failure and recovery

- PC off/asleep, Drive unmounted, Wrangler OAuth expiry or Cloudflare outage: task may fail. Static page remains, but status becomes stale after eight hours; dashboard JS refresh cannot invent fresh data.
- Reauthorize Wrangler on the local machine when OAuth expires; do not put API keys in a public repository or page.
- If source API schema changes, record per-source error class and fix collector with regression test. If deployment fails, keep previous healthy static page and record `publish-status.json` in Drive.
- GitHub Actions runner was separately blocked by a GitHub billing lock; this independent PC pair is the validated update path.
