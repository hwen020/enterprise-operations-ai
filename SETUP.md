# Setup and deployment

## Local
Use a currently supported, patched Python runtime for hosting. Local acceptance also exercises Python 3.8 compatibility. No third-party application dependency is required.

```sh
python -m venv .venv
# Activate using your platform's normal command.
python -m pip install --no-index -r requirements.txt
python -B server.py --port 8790
```

Open http://127.0.0.1:8790. Initial visitor data is seeded automatically. No password or key is required. .env.example documents public settings; it is not loaded automatically.

| Environment | Default / purpose |
| --- | --- |
| HOST | 127.0.0.1; 0.0.0.0 behind host proxy |
| PORT | 8790; provider may supply it |
| DATABASE_PATH | var/demo.sqlite3; disposable local storage |
| PUBLIC_ORIGIN | Exact HTTPS origin for custom deployment |
| RENDER_EXTERNAL_URL | Provider URL used if PUBLIC_ORIGIN absent |
| BROWSER_BIN | Optional installed Chrome/Chromium path |

```sh
python -B tools/seed_demo.py
python -B tools/verify.py
python -B tools/browser_check.py
python -B tools/public_scan.py
python -B tools/clean_check.py
```

seed_demo initializes one throwaway workspace for local inspection and never prints its secret token. Normal visitors receive their own seed. Browser checks need a separately installed Chrome/Chromium; it is not redistributed.

## Render
After final repository-owner approval:
1. Create/connect the reviewed GitHub repository.
2. Create a Blueprint from render.yaml, or one native Python web service.
3. Build: python -m pip install --no-index -r requirements.txt.
4. Start: python -B server.py.
5. HOST=0.0.0.0; provider supplies PORT. Health check /health.
6. DATABASE_PATH=/tmp/enterprise-sandbox.sqlite3.
7. RENDER_EXTERNAL_URL supplies the HTTPS origin. For a custom domain set PUBLIC_ORIGIN to the exact HTTPS URL, without trailing slash.
8. Select a currently patched supported Python runtime in provider settings. Use one instance.
9. Test fresh and incognito browsers, reset isolation, current approval gates, and a restart.
10. Only after actual cloud validation add the real Live Demo URL to README.

Verified public instance: https://enterprise-operations-ai.onrender.com

Repository: https://github.com/hwen020/enterprise-operations-ai. Public desktop, mobile, API and restart evidence is in docs/live-validation.json. The steps above describe reproduction; do not recreate the existing service.

### Free-tier data behavior
Render free services have ephemeral filesystems and may spin down on idle. Local SQLite changes are lost on redeploy, restart or spin-down. This is intentional here: reload creates a new fictional workspace when the prior database is gone. Browser refresh retains data while the file exists; ordinary local restart with the same file retains unexpired sessions.

Do not claim free-tier business durability, attach a real business database, or enable multiple independent replicas. A durable hosted store and real identity are separate future work.

References verified for the prepared configuration:
- https://render.com/docs/blueprint-spec
- https://render.com/docs/free
- https://render.com/docs/environment-variables
- https://render.com/docs/python-version

## Optional Docker
```sh
docker build -t enterprise-operations-ai .
docker run --rm -p 8790:8790 enterprise-operations-ai
```

Dockerfile runs as a non-root user. Default data is disposable. Docker build/provider deployment are not claimed tested unless separately recorded in docs/VALIDATION.md.
