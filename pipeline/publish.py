#!/usr/bin/env python3
"""Copy the built page to public/index.html and load the Supabase shim before the page script.
Run after `update.py build`."""
import os, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(ROOT, 'pipeline', 'v3', 'MR_GOLISODA_Hiring_Shortlist.html')
html = open(src, encoding='utf-8').read()
tags = ('<script src="config.js"></script>\n'
        '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.js"></script>\n'
        '<script src="claude-shim.js"></script>\n'
        '<script src="activity-log.js" defer></script>\n')
marker = '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
assert marker in html, 'page head not found'
html = html.replace(marker, marker + tags, 1)

# Messages that described the Claude runtime -> what is true on Vercel + GitHub Actions
TEXT = [
    ('Starting… (up to a minute)', 'Starting… (GitHub picks it up in about a minute)'),
    ("Sync started. It reads the new applications and resumes, then republishes this page — usually 2–15 minutes. You'll see a reload link here when it's done.",
     "Sync started. It reads the new applications, rates the resumes with Claude and redeploys this page — usually 5–20 minutes. You'll see a reload link here when it's done."),
    ('Automatic runs happen every 2 hours (10 min to the even hour: 6:50, 8:50, 10:50 …).',
     'Automatic runs happen every 2 hours (6 AM, 8 AM, 10 AM … around the clock).'),
    ('Claude Code Remote answered but refused (tool_error): ${(e&&e.message)||"no detail"}. Only the Claude account that owns the scheduled sync can start it. ${nextRun}',
     'Could not start the sync: ${(e&&e.message)||"no detail"}. Check GH_TOKEN and GH_REPO in Vercel → Settings → Environment Variables. ${nextRun}'),
]
for old, new in TEXT:
    assert old in html, 'text not found: ' + old[:50]
    html = html.replace(old, new)
os.makedirs(os.path.join(ROOT, 'public'), exist_ok=True)
open(os.path.join(ROOT, 'public', 'index.html'), 'w', encoding='utf-8').write(html)
print('public/index.html', len(html), 'bytes')
