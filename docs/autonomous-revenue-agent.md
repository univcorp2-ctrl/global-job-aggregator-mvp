# Autonomous multi-market revenue scout (2026-10-27)

This augments the existing global-job-aggregator-mvp rather than spawning a duplicate. Unattended read-only discovery and scoring runs through GitHub Actions after merge to default branch. No ChatGPT Tasks scheduler is used.

## Source and execution matrix

- Himalayas, Jobicy, Arbeitnow, Remotive, Remoshift: existing public/official job feed collection. Most opportunities are *jobs*, not subcontractable client gigs.
- Official MCP Registry: https://registry.modelcontextprotocol.io/v0.1/servers — GET metadata search, not auto-installation. New servers require source, permissions, publisher, privacy and OAuth security review.
- Apify Store API: https://api.apify.com/v2/store — GET competing Actor listings for commercial product discovery. Listing != a sale. This repo does not publish or charge products.
- Freelancer.com official OAuth project/worker API: existing optional connector, requires actual authorized token and permitted API scopes; no token is inserted by this workflow.
- Upwork and Contra official MCP: connected in separate interactive ChatGPT/OAuth contexts only; GitHub Actions does not inherit these credentials. Their writes require provider-specific prepare/confirm; never fake integration.
- New registries/vertical marketplaces: metadata reconnaissance only, no unattended sign-ups, messages or write-token installation.

## Autonomous cycle

Four times per day: run existing public-source collectors, build SQLite, search registered MCP metadata and Apify product listings, rank likely paid-project leads, generate at most 15 **draft-only** candidates, produce an auditable JSON artifact and GitHub Actions summary.

The agent explicitly sets proposed/submitted bids, hires, contracts and payments to zero. Real outcomes and worker rates are unknown until verified, so estimated net profit stays null. Feedback tuning is bounded to ±15% and only reads manually substantiated outcome counts from local data/agent-feedback.json. It never invents wins or trains its underlying model.

## Access gates

- Official write API access, account creation, OAuth/identity verification, bids consuming Connects, agency contracts, cross-platform resubcontracting, escrow, salary payments and transfers must be separately authorized and technically verified.
- Contractor/worker personal data must never be exported into this PUBLIC repository's artifacts; store sensitive opt-in records in the separate private worker DB.
- GitHub workflow uses contents:read and never exposes write or cloud provider tokens.
- Public repository Actions schedule can be delayed or disabled after 60 days of no activity. Scheduled workflow only activates after it reaches default branch; a PR does not activate it.
- Cloud artifacts are retained 7 days, not durable private commercial records or contract ledger.

## Run

python -m app.autonomous_agent --collect --output data/agent-report.json
pytest -q tests/test_autonomous_agent.py

## Acceptance criteria

- [ ] pytest on PR branch passes.
- [ ] GitHub Actions workflow completes and artifact can be opened.
- [ ] Fixed-price subcontractable *client* offers are ingested from authorized source with confirmed permission.
- [ ] Worker availability and terms verified with client subcontract approval.
- [ ] Native provider bid draft/confirm and immutable accounting reconcile with real money.
- [ ] Durable private state plus alerting configured.
- [x] Metadata discovery, score preparation and human-approval-only outbound design in code.
