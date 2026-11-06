# Trending Digest

Every morning at 8:00 IST a GitHub Action scrapes [github.com/trending](https://github.com/trending), asks Groq for a short French "explain like I'm five" explanation of each of the top 10 repos, and emails you the list.

```
GitHub Actions cron ─► docker build/run ─► scrape trending ─► README excerpts ─► Groq (ELI5) ─► Gmail SMTP ─► your inbox
```

## 1. Get the two keys (both free)

- **Groq:** create a key at https://console.groq.com/keys
- **Gmail app password:** turn on 2-Step Verification, then create an app password at https://myaccount.google.com/apppasswords. It's 16 letters. Use it here, never your normal Gmail password.

## 2. Test locally in Docker

```bash
cp .env.example .env        # then fill in your keys
docker compose build
docker compose run --rm digest --dry-run --no-llm   # scrape only, no keys needed
docker compose run --rm digest --dry-run            # + Groq, writes out/digest.html
docker compose run --rm digest                      # real run, sends the email
```

Open `out/digest.html` in a browser to see exactly what the email will look like.

### Test with a Docker Agent

`test-agent.yaml` is a [Docker Agent](https://docs.docker.com/ai/docker-agent/) QA tester that runs on Groq. It builds the image, does a dry run, and checks the output: 10 repos, valid links, star counts, and readable ELI5 text. It ends with a PASS/FAIL table and never sends email.

```bash
docker agent run test-agent.yaml --env-from-file .env --exec "run the tests"
```

## 3. Deploy on GitHub Actions

1. Push this folder to a new GitHub repo (private is fine).
2. In the repo, go to **Settings → Secrets and variables → Actions** and add these secrets:
   `GROQ_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `EMAIL_TO`
3. Two workflows are available in the **Actions** tab:
   - **Trending digest:** daily morning digest of top GitHub trending repos explained simply in French.
   - **Business radar:** runs every 2 days, scanning recent fast-growing repos and using Groq to detect micro-SaaS / business opportunities.

Tick "Dry run" first if you want to see the HTML artifact without sending an email.

After that it runs on its own every day. To change the time, edit the `cron` in `.github/workflows/digest.yml`. Cron times are in UTC, and GitHub can start scheduled runs a few minutes late.

> GitHub turns off scheduled workflows in a repo after 60 days with no commits. If the emails stop, click "Enable workflow" in the Actions tab.

## History and errors

Every run commits a dated record back to this repo, authored as you, so each day shows up as a green square on your GitHub profile.

```
logs/runs.csv                          one line per run: date, time, ok/error, mode, model, top repo
logs/history/2026/10/2026-10-15.md     that day's digest as a table plus the explanations
logs/history/2026/10/2026-10-15.json   the same data as JSON
logs/state.json                        last day an email went out
errors/2026/10/2026-10-15_083012.log   stage, error and traceback for any failed run
```

A failed run still commits its error log, so the day stays green and you can see what broke. The schedule also has backup slots at 09:00, 11:00 and 14:00 IST. GitHub sometimes runs schedules late or drops them, so a later slot retries if the 08:00 run failed or never started, and it does nothing if today's email already went out.

> Because this repo is private, the green squares only appear if your profile has **Private contributions** turned on. On your profile, open the "Contribution settings" dropdown above the contribution graph and tick it. The commit email in the workflow (`COMMIT_EMAIL`) must be an email on your GitHub account.

## Settings (env vars)

| Var | Default | |
|---|---|---|
| `TOP_N` | `10` | how many repos |
| `SINCE` | `daily` | `daily`, `weekly` or `monthly` |
| `GROQ_MODEL` | tries `openai/gpt-oss-120b`, then `qwen/qwen3.8-27b`, then `openai/gpt-oss-20b` | pin one model |
| `EMAIL_TO` | your `GMAIL_ADDRESS` | comma-separated for several people |
