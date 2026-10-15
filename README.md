# HR Screening — self-hosted (v1.6)

The same HR screening page, running on your own free accounts:

| Part | Service | Cost |
|---|---|---|
| Page + "Sync leads now" button | Vercel (Hobby) | Free |
| Sync every 2 hours (06:00, 08:00 … 04:00 IST) | GitHub Actions | Free (about 400–800 of the 2,000 free minutes a month) |
| Fit / Unfit marks, sync status | Supabase | Free |
| Resume rating (Strong / Medium / Check / Hide) | Claude API | **Paid** — prepaid credits, charged per resume |

How a sync works: GitHub Actions reads the Google Sheets → finds new applicants → Claude rates each resume →
the page is rebuilt → committed to GitHub → Vercel redeploys automatically. Nobody has to open Claude.

```
api/sync.js                  Vercel function: the Sync button starts the GitHub workflow
public/index.html            the page (rebuilt by every sync)
public/claude-shim.js        replaces the Claude runtime (marks -> Supabase, sync -> /api/sync), writes the Activity log
public/activity-log.js       the "Activity log" button and panel
sql/v1.3_activity_log.sql    Activity log table (run once in Supabase)
public/config.js             your Supabase URL + anon key  <-- edit once
apps-script/Code.gs          Google Apps Script bridge (reads sheets + resumes as the sheet owner)
pipeline/gdrive.py           talks to the bridge (or to a service account)
pipeline/fetch.py            reads the sheets
pipeline/rate.py             rates resumes with the Claude API
pipeline/update.py, v3/...   unchanged scripts from the Claude version
pipeline/runs.py             writes sync status for the page
.github/workflows/sync.yml   the schedule
supabase.sql                 database table
```

---

## Setup (about 45 minutes, once)

### 1. GitHub
1. Create a **private** repository (for example `hr-screening`).
2. Upload everything in this folder (keep the folder structure, including `.github/`).

### 2. Supabase (marks database)
1. supabase.com → New project (free).
2. SQL Editor → paste `supabase.sql` → Run. Then a new query → paste `sql/v1.3_activity_log.sql` → Run.
3. Project Settings → API: copy **Project URL** (just `https://xxxx.supabase.co`, nothing after it) and the **anon public** key.
4. Put both in `public/config.js` and commit.

### 3. Google access (reads the sheets and resumes) — use 3A

#### 3A. Apps Script bridge (recommended; works when your organisation blocks service-account keys)
1. Sign in as the account that owns the sheets and Forms (mrgolisoda2026@gmail.com) → script.google.com → **New project**. Name it `HR sync bridge`.
2. Delete the sample code, paste the whole of `apps-script/Code.gs`.
3. Change `TOKEN` (line `var TOKEN = ...`) to a long random text, e.g. `goli-7Hq2-Zp91-xK4m-2026`. Save (Ctrl+S).
4. Choose function **testSetup** → **Run** → Review permissions → choose the account → Advanced → Go to HR sync bridge → **Allow**.
   The log should show `BDE sheet rows: ...`.
5. **Deploy → New deployment** → type **Web app** → Execute as **Me** → Who has access **Anyone** → **Deploy**. Copy the **Web app URL** (ends with `/exec`).
6. These two go into GitHub secrets (step 5): `APPS_SCRIPT_URL` = the URL, `APPS_SCRIPT_TOKEN` = the TOKEN text.
   (Then you do not need `GOOGLE_SA_JSON`.)
If you edit Code.gs later: Deploy → Manage deployments → ✏️ → Version: New version → Deploy (the URL stays the same).

#### 3B. Google service account (only if your account can create keys)
1. console.cloud.google.com → create a project → APIs & Services → enable **Google Drive API**.
2. IAM & Admin → Service Accounts → Create. Open it → Keys → Add key → JSON. A `.json` file downloads.
3. Copy the service account e-mail (`...@...iam.gserviceaccount.com`) and **share with it as Viewer**,
   signed in as the sheet owner (mrgolisoda2026@gmail.com):
   - the BDE applications sheet
   - the MBA applications sheet
   - the Drive folders where the Google Forms save uploaded resumes
     (usually named "<form name> (File responses)" in the form owner's Drive)

### 4. Claude API key
console.anthropic.com → add credits → API Keys → Create key.

### 5. GitHub secrets and variables
Repository → Settings → Secrets and variables → Actions.

**Secrets**
| Name | Value |
|---|---|
| `APPS_SCRIPT_URL` | (3A) the Web app URL ending with `/exec` |
| `APPS_SCRIPT_TOKEN` | (3A) the TOKEN text you set in Code.gs |
| `GOOGLE_SA_JSON` | (3B only) the whole content of the service-account `.json` file |
| `ANTHROPIC_API_KEY` | the Claude API key |
| `SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_KEY` | Supabase anon key (same as in config.js) |

**Variables**
| Name | Value |
|---|---|
| `MBA_SHEET_ID` | `1sGCaXYi0aCuOtFLfq40QAwKBEKg-hytw9-LAdNFXKwQ` (leave empty to skip the MBA sheet) |
| `MBA_GID` | only if "All Applications" is **not** the first tab: the `gid=` number from that tab's URL |
| `BDE_GID` | only if "Applications" is not the first tab of the BDE sheet |
| `COMMIT_EMAIL` | **your GitHub account e-mail** — Vercel only deploys commits from an e-mail it recognises |
| `COMMIT_NAME` | your name |
| `CLAUDE_MODEL` | optional; default `claude-sonnet-5-5`; `claude-haiku-5-5` is cheaper |

### 6. Vercel
1. vercel.com → Add New → Project → import the GitHub repository. Framework preset: **Other**. Deploy.
2. Project → Settings → Environment Variables:
   | Name | Value |
   |---|---|
   | `GH_REPO` | `your-github-user/hr-screening` |
   | `GH_TOKEN` | GitHub → Settings → Developer settings → Fine-grained token → only this repository → permission **Actions: Read and write** |
   | `GH_BRANCH` | `main` |
3. Deployments → Redeploy (so the variables apply).

### 7. First run
GitHub → Actions → **sync** → Run workflow. When it is green, open the Vercel URL.
Then share the Vercel URL with the HR team — everyone uses that one link.

---

## Day to day
- Nothing to do. It syncs every 2 hours (06:00, 08:00, 10:00 … IST, day and night). "Sync leads now" on the page runs it at any time.
- A run that finds nothing new skips the Claude rating and finishes in about 1–2 minutes; the page is redeployed only if it changed; no Activity log row.
- To change the schedule: the `cron` line in `.github/workflows/sync.yml` (UTC; `30 */2 * * *` = every 2 hours on the even IST hour).
- A run shows on the page: "Last automatic update: …". A failed run shows the step; details are in GitHub → Actions.
- A resume Claude could not read stays "waiting" and is retried on the next run.
- Marked by: there is no login; each person picks their name from the list (as before when not signed in).

## Activity log (v1.3)
"Activity log" (next to "Sync leads now") shows who did what and when, newest first:
Marked · Changed mark (old → new) · Edited reason · Pressed Sync · Sync finished · Sync failed · Mark (before log) for marks made before v1.3.
Filter by person, action, period or search text; "Download CSV" exports what is shown.
- "Who" is the name picked in "Marked by" (no login). The Sync button uses the last name that browser picked.
- The log is insert-only: the page can add rows but cannot edit or delete them.

### Upgrade an existing v1.2 install to v1.3
1. Supabase → SQL Editor → New query → paste `sql/v1.3_activity_log.sql` → Run (creates the table and imports existing marks once).
2. On GitHub upload/replace only these files: `public/claude-shim.js`, `public/activity-log.js` (new), `pipeline/runs.py`,
   `pipeline/publish.py`, `sql/v1.3_activity_log.sql` (new), `supabase.sql`, `README.md`.
   Do NOT upload `public/index.html` from the zip: the one on GitHub has newer leads.
3. GitHub → Actions → sync → Run workflow. The run rebuilds the page with the Activity log button.

## v1.4 — every 2 hours
Upgrade from v1.3: on GitHub replace only `.github/workflows/sync.yml`, `pipeline/runs.py`, `pipeline/publish.py`, `README.md`.
No Supabase or Vercel change. Do NOT upload `public/index.html`.

## v1.5 — plant roles: Dispatch, Purchase, Production, Technician
- New applicants are also rated for TECH (Technician), PROD (Production), PUR (Purchase), DISP (Dispatch) with their own rules
  (`pipeline/new/prompt_template.txt`, "PLANT / OPERATIONS ROLES"). Applicants rated before v1.5 are not re-rated.
- 28 new positions: one per role in each franchise state (TN, AP, Telangana, Karnataka, Maharashtra, Gujarat, Jharkhand),
  "Operations · <Role> · Franchise plants", 1 seat each, recruiter "Not assigned". They match applicants anywhere in that state.
  Change seats/recruiter in `pipeline/app/positions.json` (6th value = seats) and `pipeline/app/posmeta.json` (3rd value = recruiter).
- Upgrade from v1.4: replace `pipeline/app/positions.json`, `pipeline/app/posmeta.json`, `pipeline/new/prompt_template.txt`,
  `pipeline/v3/build.py`, `pipeline/v3/page.tpl.html`, `README.md`; then Actions → sync → Run workflow. Do NOT upload `public/index.html`.

## v1.6 — MBA sheet always read
- Before v1.6 the MBA/BDM sheet was read only when the GitHub variable `MBA_SHEET_ID` was set; without it the sheet was skipped with no error.
  Now it is read by default (sheet `1sGCaXYi0aCuOtFLfq40QAwKBEKg-hytw9-LAdNFXKwQ`, first tab "All Applications"). `MBA_SHEET_ID=none` switches it off.
- Upgrade: replace `pipeline/fetch.py` and `README.md`, then Actions → sync → Run workflow.
  The first run adds every MBA application not yet on the page and rates them (one-time Claude cost).

## Notes
- Marks made on the old Claude pages are not copied here (they are stored inside those pages).
- GitHub may start scheduled runs a few minutes late when it is busy.
- To change positions or rules: edit `pipeline/app/positions.json`, `posmeta.json`, `geo.json`,
  or the rating rules in `pipeline/new/prompt_template.txt` (from "THE COMPANY'S SALES MODEL" to "LOCATION AND LANGUAGE").
