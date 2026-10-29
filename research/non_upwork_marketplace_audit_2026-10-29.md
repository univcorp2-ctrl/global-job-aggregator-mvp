# Non-Upwork freelance execution audit — 2026-10-29 (Asia/Tokyo)

## Actual result
- Platforms checked: Freelancer.com public projects, CrowdWorks Japan, Lancers public listings, Contra public terms.
- Marketplace-native **non-Upwork applications submitted: 0**, offers: 0, contracts: 0. Do **not** count drafts or catalog leads as submissions.
- Both CrowdWorks and Freelancer.com application pages were checked with read-only live browser interactions, and the sessions were **not logged in**. CrowdWorks requires member authentication, and Freelancer.com requires a logged-in bidder account. No connected provider-native bid/write API was available for these. No platform account creation, credential manipulation, off-platform DM, or bulk unsolicited contact.
- Browser sessions created for the checks were explicitly stopped and released.
- Existing Gmail contains correspondence from CrowdWorks as an employer, but that **does not prove** current freelancer login or permission to apply.
- No APIs or plugins were found that can safely submit bids under an authenticated user's Freelancer.com, CrowdWorks, Lancers or Contra account. Composio's generic jobs-search tools do not grant marketplace proposal submission.

## Shortlist (status verified from original public job pages)
| Priority | Platform | ID | Original listing | Advertised budget | Proposal competition snapshot | Verdict |
|---|---|---|---|---|---|---|
| A | Freelancer.com | 40791445 | https://www.freelancer.com/projects/data-analysis/excel-formula-repair | $15–25/hr | 5 bids in official public listing; may change | Strong fit: repair workbook lookups, exact-match QA; initial proposal $20/hr |
| A | Freelancer.com | 40791539 | https://www.freelancer.com/projects/data-analysis/custom-excel-bookkeeping-template | INR 12,500–37,500 fixed | 1 bid in public listing | Strong fit: linked bookkeeping workbook, bank reconciliation; proposed INR 18,000 and ~5 days, conditional on scope |
| A | Freelancer.com | 40791801 | https://www.freelancer.com/projects/google-sheets/Paper-Document-Summary-Spreadsheet-Entry | INR 12,500–37,500 fixed | 2 bids in public listing | AI extract with exception log; draft estimates 100 legible pages / INR 18,000, requires page count and sample confirmation |
| B | CrowdWorks | 13565423 | https://crowdworks.jp/public/jobs/13565423 | JPY 50,000–100,000 fixed | 66 applications, 0 contracts at audit time | Monthly facility-blog summarization with source-claim provenance checking; proposed JPY 80,000 subject to scope/acceptance |
| B | CrowdWorks | 13565767 | https://crowdworks.jp/public/jobs/13565767 | JPY 400,000–500,000 fixed | 77 applications, 0 contracts | Entire 5-stage food stock/expiration/reminder system required; not a small trial, all implementation/test/maintenance must be in quote; speculative JPY 480,000 requires full data/environment assessment |
| C | CrowdWorks | 13488036 | https://crowdworks.jp/public/jobs/13488036 | JPY 500,000 per client contract, no guaranteed pay | 14 applicants, 2 contractors at audit time | Sales referral work rather than autonomous implementation. No unsolicited outreach; require detailed commission criteria and consent |

### Exclusions / corrections
- CrowdWorks 13565468 initially looked AI-friendly but it pays **JPY 0.1 per valid company** and **explicitly bans unattended automation/macros**. Exclude for unit economics and client rules.
- CrowdWorks 13566261 Excel data research had a future-sounding deadline but its live page explicitly states **募集終了**. Exclude.
- CrowdWorks 13564950 AI SEO software listing became **private/unviewable** in live fetch; not a verified open opportunity. Exclude.
- CrowdWorks 13535831 AI tutor listing requires specific marketing years and exclusive post-contract teaching restrictions; don't assert user meets them. Not AI-first / high lock-in.
- Freelancer.com 40785192 xlwings add-in requires a specific Microsoft 365 Excel version, delivered .xlam track record and Chinese locale testing; the personal experience prerequisites are not verified. Do not fabricate a prior delivered add-in.
- Generic CrowdWorks Excel data entry can be low pay or 20+ hours per week; prioritize bounded AI work over low-margin manual assignments.

## Source of truth and drafts
- Private managed spreadsheet: https://docs.google.com/spreadsheets/d/1UdGLaaf_Kcp8W77_80PP_7w1AVv0HcmhcP65LU_713k/edit
- The native sheet `非Upwork_案件審査_20261029` has 6 individually reviewed rows.
- The native sheet `非Upwork_提案文_20261029` has 5 detailed **unsent** proposals, scope assumptions, and proposed fixed/ hourly amounts.
- The native sheet `非Upwork_媒体接続障害` records marketplace authentication/write-scope prerequisites.
- The private unified job catalog adds only 3 new CrowdWorks entries (Freelancer listings were already in the catalog); 174 rows total as a dated snapshot.

## Practical next action
Authenticate the worker/bidder account in each marketplace through a supported, user-approved session. Then **for each exact project**, recheck open/closed, no prior bid, platform costs, permitted AI processing and subcontract rules; submit one personalized proposal; capture the actual platform receipt; update the source-of-truth Sheets/Notion. Do not treat the general job-search integration as an authorized submission API or claim any contract is awarded.
