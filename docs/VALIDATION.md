# Validation and release-readiness evidence

## Executed locally
| Check | Result | Evidence |
| --- | --- | --- |
| Automated regressions | 21 passed; zero failures/errors/skips | test-validation.json |
| Desktop browser, 1440px | 30 checks passed | browser-validation.json |
| Mobile browser, 390px | 32 checks passed | browser-validation.json |
| Clean-directory offline virtual environment install | Passed | clean-validation.json |
| Fresh initialization and no-key start | Passed | clean-validation.json |
| Retained SQLite restart | Existing visitor state retained | clean-validation.json |
| Lost-filesystem simulation | Old cookie rejected; fresh seed created | clean-validation.json |
| Cross-visitor object access and reset | Blocked / isolated | tests and clean-validation.json |
| Source, secrets, restricted phrases, dependency inventory | Zero findings | security-validation.json |
| Git history | All reachable commit blobs and metadata scanned; no findings | tools/public_scan.py --history |

The browser acceptance covers seeded Dashboard, CRM create/search/empty/stage/timeline, CSV preview and atomic import, quotation creation, Decimal totals, new revision and comparison, Reviewer switching, quotation approval, campaign linkage, unapproved execution rejection, current campaign approval, simulated results, exclusion evidence, complete workflow steps, persisted invalid-import error, Analytics, browser reload, own-workspace reset, and mobile navigation/overflow.

All business test records are fictional and all API/browser tests use disposable local databases. The screenshots were rendered from this project's UI, not obtained from a third-party site. Image metadata is scanned; manual image review remains part of owner publication approval.

The clean copy is assembled from the public file inventory into a new temporary directory and virtual environment, installed using pip --no-index, initialized, tested and started without inherited credentials. Persistence tests stop/restart the child service with the same file, then model ephemeral file loss using a separate fresh database path. This is not an actual hosting-provider deployment.

## Public deployment acceptance
The application is published at https://enterprise-operations-ai.onrender.com from https://github.com/hwen020/enterprise-operations-ai. Public testing passed 30 desktop and 32 mobile browser checks, 33 API/security/isolation checks and an actual restart/reseed check. Runtime exceptions and unexpected HTTP 5xx responses were zero during browser checks. See live-validation.json.

The initial browser attempt stopped at a role-switch timing race in the test driver. The resumed driver retained all business assertions and additionally waited for the Reviewer approval button to become enabled. It did not change application permissions or suppress errors.

## Not executed / not claimed
- No Docker build without an available engine.
- No real LLM, email, CRM, carrier, payment or business API integration.
- No claim of production identity, durable free-tier storage or exhaustive legal/secret certification.

## Reproduction
Run tools/verify.py, tools/browser_check.py, tools/public_scan.py and tools/clean_check.py. After committing, run tools/public_scan.py --history. Raw diagnostics stay in ignored .local/; public JSON summaries omit machine paths, credentials and cookie values.

The owner authorized publication and deployment. Future releases must repeat the license, provenance, content and history checks. Mock personas and outcomes remain explicit; production identity and durable business storage are not claimed.
