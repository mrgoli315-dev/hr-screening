#!/usr/bin/env python3
"""Turn a saved Google Drive download_file_content result (CSV export of the BDE sheet) into a plain list of rows.
Usage: python3 pipeline/sheet_csv.py <saved tool result .txt/.json, or a raw .csv> <out.json>
"""
import json, base64, csv, io, sys
src, out = sys.argv[1], sys.argv[2]
raw = open(src, encoding='utf-8').read()
try:
    d = json.loads(raw)
    if isinstance(d, list) and d and isinstance(d[0], dict) and 'text' in d[0]:
        d = json.loads(d[0]['text'])
    text = base64.b64decode(d['content']).decode('utf-8')
except Exception:
    text = raw
rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
json.dump(rows, open(out, 'w'), ensure_ascii=False)
print('rows', len(rows), 'last', rows[-1][:3] if rows else None)
