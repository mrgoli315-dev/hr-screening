#!/usr/bin/env python3
"""Download the application sheets as rows for `update.py append`.

Env:
  BDE_SHEET_ID  (default: Mr. GoliSoda BDE Applications)
  BDE_GID       optional tab gid; empty = first tab ("Applications")
  MBA_SHEET_ID  default: Mr. GoliSoda BDM/MBA Applications; "none" = skip the MBA sheet
  MBA_GID       optional tab gid; empty = first tab
Writes work/bde_rows.json and (if MBA_SHEET_ID is set) work/mba_rows.json.
"""
import csv, io, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdrive

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, 'work')
os.makedirs(WORK, exist_ok=True)


def rows_of(text):
    return [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]


def save(name, sheet_id, gid):
    rows = rows_of(gdrive.sheet_csv(sheet_id, gid))
    path = os.path.join(WORK, name)
    json.dump(rows, open(path, 'w'), ensure_ascii=False)
    print(name, 'rows', len(rows), 'last', rows[-1][:3] if rows else None)


bde = os.environ.get('BDE_SHEET_ID') or '1Esi7wAV-Yyh8uasE2qmzaoArGMPsovQcvAXdog_XzQU'
save('bde_rows.json', bde, os.environ.get('BDE_GID'))
# v1.6: the MBA sheet is always read (it was skipped silently when the MBA_SHEET_ID variable was not set).
# Set MBA_SHEET_ID only to read a different sheet; set it to "none" to switch the MBA sheet off.
mba = (os.environ.get('MBA_SHEET_ID') or '1sGCaXYi0aCuOtFLfq40QAwKBEKg-hytw9-LAdNFXKwQ').strip()
if mba.lower() != 'none':
    save('mba_rows.json', mba, os.environ.get('MBA_GID'))
else:
    print('MBA sheet switched off (MBA_SHEET_ID=none)')
