"""Google Drive access with a service account (read only).

Env:
  GOOGLE_SA_JSON   the full JSON key of the service account (paste the whole file content as a GitHub secret)

Share these with the service account e-mail (Viewer):
  - the BDE applications sheet
  - the MBA applications sheet
  - the Drive folder(s) where the Google Form saves uploaded resumes
"""
import io, json, os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import AuthorizedSession

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


def _creds():
    raw = os.environ.get('GOOGLE_SA_JSON', '').strip()
    if not raw:
        raise SystemExit('GOOGLE_SA_JSON is not set')
    return service_account.Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)


_drive = None
_session = None


def drive():
    global _drive
    if _drive is None:
        _drive = build('drive', 'v3', credentials=_creds(), cache_discovery=False)
    return _drive


def session():
    global _session
    if _session is None:
        _session = AuthorizedSession(_creds())
    return _session


def sheet_csv(file_id, gid=None):
    """CSV text of one tab. Without gid: the first tab (Drive export)."""
    if gid not in (None, ''):
        url = 'https://docs.google.com/spreadsheets/d/%s/export?format=csv&gid=%s' % (file_id, gid)
        r = session().get(url, timeout=120)
        r.raise_for_status()
        return r.content.decode('utf-8')
    data = drive().files().export_media(fileId=file_id, mimeType='text/csv').execute()
    return data.decode('utf-8')


def meta(file_id):
    return drive().files().get(fileId=file_id, fields='id,name,mimeType,size', supportsAllDrives=True).execute()


def download(file_id):
    buf = io.BytesIO()
    req = drive().files().get_media(fileId=file_id, supportsAllDrives=True)
    dl = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue()


def export_text(file_id):
    """Google Docs -> plain text."""
    return drive().files().export_media(fileId=file_id, mimeType='text/plain').execute().decode('utf-8', 'replace')
