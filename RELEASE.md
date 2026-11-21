# Release preparation

Status: published after owner authorization.

Repository: https://github.com/hwen020/enterprise-operations-ai

Live Demo: https://enterprise-operations-ai.onrender.com

Public acceptance evidence: docs/live-validation.json. The existing service is Free. Do not recreate either resource when maintaining this release.

## Before public release
1. Review README, screenshots, provenance inventory and MIT license. Confirm release rights.
2. Run tools/verify.py, tools/browser_check.py, tools/clean_check.py and tools/public_scan.py.
3. Review git status, git diff --cached and all staged paths. Never force-add ignored files.
4. Commit only the source, tests, docs, authored assets and fictional fixtures.
5. Run tools/public_scan.py --history after committing. Review reachable commit metadata too.
6. Keep Live Demo explicitly undeployed until a real cloud instance passes validation.

## Create GitHub repository (manual, after approval)
Create an empty repository named enterprise-operations-ai in the approved account. Do not initialize it with another README, license or unrelated history. Start Private if the final visibility review is not complete.

Suggested description: Agentic workflow automation sandbox with isolated visitors, versioned quotations, human approvals, rule agents and simulated analytics.

After reviewing the remote URL and contents:
```sh
git remote add origin https://github.com/YOUR_ACCOUNT/enterprise-operations-ai.git
git branch -M main
git push -u origin main
```

The commands above are reference instructions for a new checkout. This repository already has the reviewed personal GitHub origin and is Public. Do not add a second remote or repeat repository creation.

## Render (after separate deployment approval)
Follow SETUP.md using render.yaml. Verify HTTPS cookies, two-browser isolation, approval blocks, reset, health, error traces and restart reseeding. Record the deployed revision and actual URL. Then update the README Live Demo field. The verified URL is listed above; cloud tests and the actual restart check passed.

## Suggested initial release notes
Enterprise Operations AI / Portfolio MVP:
- Six connected modules and responsive 1440px/390px UI.
- Isolated expiring workspaces with fictional starter data.
- Immutable Decimal quotation snapshots and version comparison.
- Audience exclusion evidence and revision-bound approvals.
- Explicit local rule agents, traceable errors, idempotent simulation and analytics.
- No external email, model inference, real orders or business API connections.

Limitations: disposable free-host storage; simulated personas; USD/single-product quotes; no production identity, team tenancy or cloud durability claim.
