# HR Screening — self-hosted (v1.0)

The same HR screening page, running on your own free accounts:

| Part | Service | Cost |
|---|---|---|
| Page + "Sync leads now" button | Vercel (Hobby) | Free |
| Sync twice a day (06:00 and 18:00 IST) | GitHub Actions | Free |
| Fit / Unfit marks, sync status | Supabase | Free |
| Resume rating (Strong / Medium / Check / Hide) | Claude API | **Paid** — prepaid credits, charged per resume |

How a sync works: GitHub Actions reads the Google Sheets → finds new applicants → Claude rates each resume →
the page is rebuilt → committed to GitHub → Vercel redeploys automatically. Nobody has to open Claude.

```
api/sync.js                  Vercel function: the Sync button starts the GitHub workflow
public/index.html            the page (rebuilt by every sync)
public/claude-shim.js        replaces the Claude runtime (marks -> Supabase, sync -> /api/sync)
public/config.js             your Supabase URL + anon key  <-- edit once
pipeline/fetch.py            reads the sheets (Google service account)
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
2. SQL Editor → paste `supabase.sql` → Run.
3. Project Settings → API: copy **Project URL** and the **anon public** key.
4. Put both in `public/config.js` and commit.

### 3. Google service account (reads the sheets and resumes)
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
| `GOOGLE_SA_JSON` | the whole content of the service-account `.json` file |
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
- Nothing to do. It syncs at 06:00 and 18:00 IST. "Sync leads now" on the page runs it at any time.
- A run shows on the page: "Last automatic update: …". A failed run shows the step; details are in GitHub → Actions.
- A resume Claude could not read stays "waiting" and is retried on the next run.
- Marked by: there is no login; each person picks their name from the list (as before when not signed in).

## Notes
- Marks made on the old Claude pages are not copied here (they are stored inside those pages).
- GitHub may start scheduled runs a few minutes late when it is busy.
- To change positions or rules: edit `pipeline/app/positions.json`, `posmeta.json`, `geo.json`,
  or the rating rules in `pipeline/new/prompt_template.txt` (from "THE COMPANY'S SALES MODEL" to "LOCATION AND LANGUAGE").
