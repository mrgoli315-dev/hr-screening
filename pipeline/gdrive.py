"""Read the application sheets and resume files from Google Drive (read only).

Two ways — the first one that is configured is used:

A) Apps Script bridge (no Google Cloud key needed)   <- use this when service-account keys are blocked
   APPS_SCRIPT_URL    the web-app URL of apps-script/Code.gs (ends with /exec)
   APPS_SCRIPT_TOKEN  the TOKEN text set inside Code.gs

B) Service account
   GOOGLE_SA_JSON     the full JSON key of a service account that the sheets and resume folders are shared with
"""
import base64, io, json, os
import requests

AS_URL = os.environ.get('APPS_SCRIPT_URL', '').strip()
AS_TOKEN = os.environ.get('APPS_SCRIPT_TOKEN', '').strip()
USE_BRIDGE = bool(AS_URL)


# ---------------------------------------------------------------- A) Apps Script bridge
def _bridge(action, file_id, **extra):
    params = {'token': AS_TOKEN, 'action': action, 'id': file_id}
    params.update({k: v for k, v in extra.items() if v not in (None, '')})
    last = None
    for attempt in range(3):
        try:
            r = requests.get(AS_URL, params=params, timeout=300, allow_redirects=True)
            r.raise_for_status()
            try:
                out = r.json()
            except ValueError:
                raise RuntimeError('Apps Script did not return JSON (check the deployment: Execute as Me, access Anyone): '
                                   + r.text[:200])
            if not out.get('ok'):
                raise RuntimeError('Apps Script: ' + str(out.get('error')))
            return out['data']
        except RuntimeError:
            raise
        except Exception as e:  # network hiccup: retry
            last = e
    raise RuntimeError('Apps Script unreachable: %s' % last)


# ---------------------------------------------------------------- B) service account
_drive = None
_session = None


def _creds():
    from google.oauth2 import service_account
    raw = os.environ.get('GOOGLE_SA_JSON', '').strip()
    if not raw:
        raise SystemExit('Set APPS_SCRIPT_URL + APPS_SCRIPT_TOKEN (or GOOGLE_SA_JSON)')
    return service_account.Credentials.from_service_account_info(
        json.loads(raw), scopes=['https://www.googleapis.com/auth/drive.readonly'])


def _drv():
    global _drive
    if _drive is None:
        from googleapiclient.discovery import build
        _drive = build('drive', 'v3', credentials=_creds(), cache_discovery=False)
    return _drive


def _sess():
    global _session
    if _session is None:
        from google.auth.transport.requests import AuthorizedSession
        _session = AuthorizedSession(_creds())
    return _session


# ---------------------------------------------------------------- public functions (same for A and B)
def sheet_csv(file_id, gid=None):
    """CSV text of one tab. Without gid: the first tab."""
    if USE_BRIDGE:
        return _bridge('sheet', file_id, gid=gid)
    if gid not in (None, ''):
        url = 'https://docs.google.com/spreadsheets/d/%s/export?format=csv&gid=%s' % (file_id, gid)
        r = _sess().get(url, timeout=120)
        r.raise_for_status()
        return r.content.decode('utf-8')
    return _drv().files().export_media(fileId=file_id, mimeType='text/csv').execute().decode('utf-8')


def meta(file_id):
    if USE_BRIDGE:
        return _bridge('meta', file_id)
    return _drv().files().get(fileId=file_id, fields='id,name,mimeType,size', supportsAllDrives=True).execute()


def download(file_id):
    if USE_BRIDGE:
        return base64.b64decode(_bridge('file', file_id))
    from googleapiclient.http import MediaIoBaseDownload
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, _drv().files().get_media(fileId=file_id, supportsAllDrives=True))
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue()


def export_text(file_id):
    """Google Docs -> plain text."""
    if USE_BRIDGE:
        return _bridge('text', file_id)
    return _drv().files().export_media(fileId=file_id, mimeType='text/plain').execute().decode('utf-8', 'replace')
