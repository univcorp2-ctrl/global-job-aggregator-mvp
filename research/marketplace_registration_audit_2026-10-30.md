# Marketplace account registration and verified bid-path audit — 2026-10-30

## Operating goal
User has explicitly requested registration (where appropriate) on freelance sites and high-quality applications, including worldwide fixed-price jobs, using their authorized Google Drive registration policy. Do not create duplicate accounts, buy credits without approval, misstate marketplace proposal status or publish credentials.

## Source of truth (private, do not copy secrets into GitHub)
- Google Drive native spreadsheet: https://docs.google.com/spreadsheets/d/1ULCcjgjeM0nWV8Wf9SUlMEDf6Dq0ogmMiCv966F0BIo/edit
- New restricted operations tab: https://docs.google.com/spreadsheets/d/1ULCcjgjeM0nWV8Wf9SUlMEDf6Dq0ogmMiCv966F0BIo/edit#gid=8873301
- The spreadsheet tabs "Email Regitration Rul", "Registration Rule", "Confidential My Information" and "WebService" define accurate identity/organization/email selections. Do not export these tabs to public repositories.
- Official registration policy reserves the non-real-estate account for general freelance marketplaces; the real estate contact account is only for actual property activity.
- Existing CrowdWorks account is present in the user's WebService registration records. **Do not create another.**
- The Google Drive folder literally named "private" has a Messenger child folder, and provider metadata reports owner plus writer sharing. It is NOT the actual marketplace registration database and is not an appropriate place to add plaintext passwords.

## Live official registration interfaces
| Provider | Official entry point | Existing registration? | Registration completed in this audit | Official bid submission available in current MCP connections? |
| --- | --- | --- | --- | --- |
| CrowdWorks | https://crowdworks.jp/login | Account record in user's private spreadsheet | No new account (avoid duplicate) | No authenticated bidder session / verified write API |
| PeoplePerHour | https://www.peopleperhour.com/site/register | No verified user account; absence of email records is not proof of nonexistence | No; live browser signup action blocked | No |
| Freelancer.com | https://www.freelancer.com/signup | Not verified | No | Official API exists, but user OAuth/bid-write permission not authorized |
| Lancers Japan | https://www.lancers.jp/user/sign_up | Not verified | No | No bidder submit integration verified |
| Contra | https://contra.com/ | Not verified | No | No bidder write API |
| Get on Board | https://www.getonbrd.com/ | Not verified | No | Public recruiting feeds differ from candidate application authorization |

PeoplePerHour official help: https://support.peopleperhour.com/hc/en-us/articles/205217567-Submitting-Proposals and https://www.peopleperhour.com/static/manual (freelancer approval normally up to 7 working days, optional paid fast-track). Its terms https://www.peopleperhour.com/static/terms bar multiple user accounts. The Cotlet non-official MCP https://github.com/cotletdev/peopleperhour-api-mcp-server is not a substitute for obtaining native user account and permission to bid. Freelancer.com's developer site https://developer.freelancer.com/ exists; search/harvesting is not verified proposal submission. Lancer.app's official MCP https://lancer.app/for-agents supports Upwork exclusively; it is unrelated to Japanese Lancers.

## Live direct-contract targets
- Stivate Automation Engineer: https://www.stivate.com/careers/automation-engineer. Official company email application route with CV/portfolio/experience. Role accepts remote hourly, project and retainer contracts. A professional English CV was created in private Google Docs for the user, but sharing it externally was blocked by host safety checks; no submission or message receipt was obtained. Do not invent one.
- Extery AI engineer / training partner: https://extery.jp/career/ — official direct contact form, application not submitted due to interaction constraints.
- Solara AI/DX contract partner: https://solara.co.jp/recruit/jobs/dx-partner-contract — temporarily suspended as of Oct 30, 2026; exclude from active shortlist.

## Connection state and truthful outcomes
- Composio Gmail has an ACTIVE non-real-estate sender connection, independently discovered through toolkit account enumeration; however using it to create an external application draft was blocked by the host safety checks. Do not reroute through another provider to evade a safety decision.
- Local Chrome Browser MCP is disconnected; the originating-browser extension isn't available. No unverified login cookies or credentials should be transmitted to a remote scraping browser.
- Official new marketplace registrations in this audit: **0**.
- New officially accepted applications after this audit began: **0**.
- Professional CV preparation: **1 private Google Doc**, not publicly shared.
- Private registration audit tab: **9 provider/status rows**, Google Drive API readback verified.
- Notion command/report pages updated with these facts. No credentials, passwords, OTP, account recovery links, contact phone numbers or personal postal addresses are present in this public repo file.

## Safe completion gate
1. Match the platform with the real existing user account and approved registration email.
2. Complete its own credential-creation / OAuth / MFA process through an authorized user session. Stop at CAPTCHA/identity verification; never bypass.
3. Verify platform onboarding success, registered account owner and the freelancer role.
4. Re-read one specific open job and price / listing status, prepare a grounded individual bid.
5. Submit through the authenticated official site/provider tool, retain actual receipt ID.
6. Update the private job/applications sheet and Notion; never count a draft or external site form navigation as a bid.
