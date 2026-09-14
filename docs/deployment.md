# Railway deployment

The repository includes a Dockerfile that installs the locked production dependencies
with uv and starts one server on `0.0.0.0:$PORT` (8000 locally).
The build context excludes local credentials, personal data, and development files.

## Service setup

1. Create a Railway service from `neocortex/wanna-watch`, branch `main`.
2. Attach a persistent volume mounted at `/data`. The image sets
   `WANNA_WATCH_DATA_DIR=/data`; SQLite and downloaded IMDb data live there.
3. Add `TMDB_READ_TOKEN` as a Railway service variable. Never put it in the image
   or repository.
4. Set a strong `WANNA_WATCH_PASSWORD` service variable. The browser login username
   is `watch`. Railway startup refuses to run without a password.
5. Keep one replica, disable service sleeping, and use `/healthz` as the healthcheck.
6. Deploy, generate a Railway HTTPS domain, and sign in. Verify `/api/status`
   requires credentials and `/healthz` responds successfully.

HTTP Basic authentication protects the app, static assets, API, and API documentation.
Only `/healthz` is public and returns a simple readiness response. Always use HTTPS
for remote access. Cross-site writes are rejected. To rotate the password, update
`WANNA_WATCH_PASSWORD` and redeploy; the browser will prompt for the new password.
This remains a single shared personal account, with no per-user histories.

A fresh volume starts with an empty catalog. Select subscriptions and refresh after
setup; collection can take tens of minutes. A local database is not copied into the
image. Back up the volume before deleting the service or volume, and avoid deploying
during an active catalog refresh. Restarting preserves the published catalog but
does not resume an interrupted collection.

## Local image check

```bash
docker build -t wanna-watch:railway .
docker run --rm -p 8000:8000 --env-file .env \
  -v wanna-watch-data:/data wanna-watch:railway
```

Visit `http://localhost:8000`. The named volume survives container removal.
