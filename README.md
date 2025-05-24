# Functional Job Automation
*A streamlined, hardened fork of “Auto Job Applier for LinkedIn”*

> **Upstream project:** <https://github.com/GodsScion/Auto_job_applier_linkedIn>  
> This fork preserves the core Easy-Apply bot **and** adds a live status‑tracking
> dashboard, crash‑safe runtime features, free‑AI fallback, proxy rotation,
> tidier file layout, and secret‑safe configuration.  
> Everything else (installers, usage, licence) still works exactly the same.

---

## Why this fork? — Key upgrades

| Feature | Upstream | **Functional Job Automation** |
|---------|----------|--------------------------------|
| **Live dashboard** | Basic totals page | Full Flask UI (`app.py`) lists every job, status, résumé link & log tail in real time |
| **Smart résumé generator** | GPT rewrites a PDF in place | `src/document_generator/resume_maker.py` rebuilds bullets per job spec, then exports a fresh PDF |
| **AI‑agnostic & free fallback** | Toggle OpenAI / DeepSeek | Point `llm_api_url` at *any* OpenAI‑compatible endpoint (local Llama, Groq, etc.). If no key is set, bot uses a built‑in **FreeAIClient**—zero cost |
| **Crash‑safe runs** | — | Progress bars (`tqdm`), checkpoints, detailed `status_manager.log`; resume a 1 000‑job spree after interruption |
| **Email → status auto‑update** | Simple CSV append | `app_tracker.py` + `modules/tracking/` parse Gmail, Yahoo, Outlook, update dashboard & log |
| **Proxy & rate‑limit handling** | Minimal | Central `src/utilities/proxies.py` rotates a list or remote feed; every Chrome session & LLM call can use a new proxy |
| **Secret‑safe repo** | Keys once lived in history | All creds live in `.env`; `config/secrets_example.py` documents required fields—nothing sensitive ever hits GitHub |
| **Windows 1‑click setup** | `.bat` script | Signed `windows-setup.ps1` installs Python, Chrome, Chromedriver and caches your GitHub PAT |

---

## Quick‑start

```bash
# 1 — clone
git clone https://github.com/OPKYEI/FunctionalJobAutomation.git
cd FunctionalJobAutomation

# 2 — install deps (or run the PowerShell installer)
pip install -r requirements.txt

# 3 — add your secrets
cp config/secrets_example.py config/secrets.py
#   OR copy .env.example → .env and fill in:
#   OPENAI_API_KEY=sk-...
#   EMAIL_USERNAME=...
#   EMAIL_PASSWORD=...
#   ...

# 4 — configure your searches
edit config/search.py          # keywords, location, filters
edit config/questions.py       # canned answers

# 5 — run the bot
python runAiBot.py
# visit http://localhost:5000 to watch jobs & statuses in real time
```

> **No OpenAI key?** Leave `OPENAI_API_KEY` blank—the bot automatically falls
> back to the bundled FreeAI client (slower but free).

---

## Advanced components

### 1 · Live status tracker `app_tracker.py`

`app_tracker.py` polls your mailbox for LinkedIn status e‑mails, updates a CSV
or SQLite ledger, and feeds the dashboard served by `app.py`.

| Step | Command / setting | Notes |
|------|-------------------|-------|
| Configure accounts | Edit **`EMAIL_ACCOUNTS`** in `config/secrets.py` or `.env` | Works with Gmail, Yahoo, Outlook (use App Passwords with MFA). |
| One‑shot run | `python app_tracker.py` | Poll once, print summary, exit. |
| Continuous mode | `python app_tracker.py --watch 300` | Poll every 300 s (5 min). |
| Extra flags | `--no-desktop`, `--csv PATH`, `--sqlite PATH`, `--folder NAME` |
| Log file | `status_manager.log` | Rolling 1 MB file with timestamps. |
| Windows service | `setup/windows-setup.ps1` offers to create a scheduled task (`FJA-Tracker`). |

### 2 · Free‑AI client & proxy rotation

#### 2.1 Free‑AI client
If `OPENAI_API_KEY` is empty the bot uses **FreeAIClient**
(`src/utilities/free_ai_client.py`) which calls  
`https://api.freegpt.com/v1/chat/completions`.

| Variable | Purpose | Default |
|----------|---------|---------|
| `FREE_AI_BASE_URL` | Override endpoint | (see above) |
| `FREE_AI_MODEL` | Model slug | `gpt-3.5-turbo` |
| `FREE_AI_MAX_TOKENS` | Safety cap | `2048` |

Automatic retries: 3 attempts, 2‑second back‑off.

#### 2.2 Proxy list
Add proxies (one per line, `http://user:pass@host:port`) to `proxies.txt` or set
a remote feed in `PROXY_LIST_URL`.  Enable in `.env`:

```
USE_PROXIES=true
PROXY_MODE=round_robin   # or random
```

Every Chrome session and every LLM request will pick the next proxy.

---

### FAQ

<details><summary>Does the tracker work with custom e‑mail folders?</summary>
Yes. Default is **INBOX**. Pass `--folder "LinkedIn"` or set `EMAIL_FOLDER` in
`.env`.
</details>

<details><summary>Can I disable AI entirely?</summary>
Set `use_AI = False` in `config/secrets.py` *and* leave `OPENAI_API_KEY` blank.
The bot just attaches your static résumé.
</details>

<details><summary>Is the Free‑AI endpoint rate‑limited?</summary>
Yes—about 20 req/min per IP. The client delays & retries automatically.
Heavy users should run their own LLM or use an OpenAI/DeepSeek key.
</details>

---

## File layout (fork‑specific)

```
FunctionalJobAutomation/
├─ app.py                       ← Live dashboard
├─ app_tracker.py               ← E‑mail → status updater
├─ resume_customizer.py         ← Stand‑alone résumé rewriter
├─ modules/…                    ← Selenium helpers, AI calls, tracking
├─ src/
│   ├─ config/…                 ← Python settings (mirrors .env)
│   ├─ document_generator/…     ← Tailor‑made résumé builder
│   ├─ processor/…              ← GPT / LLM wrappers
│   ├─ scraper_linkedin/…       ← Manager + scraper split
│   └─ utilities/…              ← proxies, FreeAI client, misc tools
├─ setup/                       ← Windows / macOS / Linux installers
├─ config/…                     ← Search, questions, templates
└─ requirements*.txt
```

---

## Roadmap

* Cookie‑based LinkedIn login (no password storage)  
* Docker image with headless Chrome & self‑hosting out of the box  
* Telegram / Slack notifications for interview invites

Contributions welcome—open an issue or PR.

---

© 2025 Simon Gyimah · Forked from Sai Vignesh Golla · AGPL‑3.0
