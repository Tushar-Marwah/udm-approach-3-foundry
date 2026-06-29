# Deploying the AmploFly4.0 UDM demo

The app is a single Flask process (SQLite, no external DB). It seeds itself on first
boot, so a fresh container comes up fully populated. Two ways to share it:

---

## A) Instant link (no account) — Cloudflare quick tunnel

Runs on your Mac; the link is live only while your machine + the server are running.

```bash
cd backend && python3 app.py          # terminal 1 — starts the app on :5050
./cloudflared tunnel --url http://localhost:5050   # terminal 2 — prints a public https URL
```

(The `cloudflared` binary is already downloaded; if missing, grab it from
https://github.com/cloudflare/cloudflared/releases for `darwin-arm64`.)

---

## B) Permanent link — Render (recommended) or Railway

Stays up 24/7 even when your laptop is off. ~10 minutes, needs your own free account.

### Render (Docker blueprint — easiest)
1. Push this folder to a **GitHub repo** (see below).
2. Go to **render.com → New → Blueprint**, pick the repo. It reads `render.yaml`.
3. When prompted, set the secret **`MAGICA_API_KEY`** = your Magica key.
4. Click **Apply**. First build takes a few minutes; you get a `*.onrender.com` URL.

> Free Render web services sleep after ~15 min idle and cold-start on the next
> visit (~30s). Upgrade to a paid instance to keep it always-on.

### Railway (alternative)
1. Push to GitHub.
2. **railway.app → New Project → Deploy from GitHub repo.** It auto-detects the `Dockerfile`.
3. In **Variables**, add `MAGICA_API_KEY` and `HOST=0.0.0.0`.
4. Generate a domain under **Settings → Networking**.

### Push to GitHub (one-time)
```bash
# a local git repo + first commit already exist (see below)
gh repo create amplofly-udm --private --source=. --push   # if you have the gh CLI
# — or — create an empty repo on github.com, then:
git remote add origin https://github.com/<you>/amplofly-udm.git
git push -u origin main
```

---

## Notes
- **`.env` is NOT committed** (it's git-ignored). Set `MAGICA_API_KEY` as an env var on the host instead.
- **The AI is public.** Anyone with the link can run the agent/ingest, which spends your
  Magica credits. To gate it, put the host behind a password (Render: add HTTP Basic Auth
  via a small middleware, or use Cloudflare Access on a named tunnel).
- **Uploads** (registry of files added at runtime) live in `data/` and are **not** persisted
  across redeploys on free tiers — attach a persistent disk/volume if you need them to stick.
- Port: the app reads `$PORT` (cloud platforms inject it) and binds `$HOST` (set `0.0.0.0`).
