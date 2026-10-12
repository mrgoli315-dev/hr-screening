/**
 * HR sync bridge — paste into a new Apps Script project (script.google.com) while signed in as the
 * account that owns the application sheets and the Form resume folders (mrgolisoda2026@gmail.com).
 * Deploy -> New deployment -> Web app -> Execute as: Me, Who has access: Anyone.
 *
 * The GitHub sync calls:
 *   ?token=T&action=sheet&id=<sheetId>[&gid=<tab gid>]   -> CSV text of the tab (first tab if no gid)
 *   ?token=T&action=meta&id=<fileId>                     -> {name, mimeType, size}
 *   ?token=T&action=file&id=<fileId>                     -> base64 of the file
 *   ?token=T&action=text&id=<googleDocId>                -> plain text of a Google Doc
 * Every reply is JSON: {"ok":true,"data":...} or {"ok":false,"error":"..."}.
 */

// Change this to any long random text, and put the SAME text in the GitHub secret APPS_SCRIPT_TOKEN.
var TOKEN = "goli-7Hq2-Zp91-xK4m-2026";

function doGet(e) {
  var p = (e && e.parameter) || {};
  try {
    if (p.token !== TOKEN) throw new Error("bad token");
    var id = p.id;
    if (!id) throw new Error("id missing");
    var data;
    if (p.action === "sheet") data = sheetCsv_(id, p.gid);
    else if (p.action === "meta") data = fileMeta_(id);
    else if (p.action === "file")
      data = Utilities.base64Encode(
        DriveApp.getFileById(id).getBlob().getBytes(),
      );
    else if (p.action === "text")
      data = DocumentApp.openById(id).getBody().getText();
    else throw new Error("unknown action");
    return reply_({ ok: true, data: data });
  } catch (err) {
    return reply_({ ok: false, error: String((err && err.message) || err) });
  }
}

function sheetCsv_(id, gid) {
  var ss = SpreadsheetApp.openById(id);
  var sh = ss.getSheets()[0];
  if (gid !== undefined && gid !== "") {
    var found = ss.getSheets().filter(function (s) {
      return String(s.getSheetId()) === String(gid);
    });
    if (!found.length) throw new Error("tab gid " + gid + " not found");
    sh = found[0];
  }
  var rows = sh.getDataRange().getDisplayValues();
  return rows
    .map(function (r) {
      return r
        .map(function (v) {
          return '"' + String(v).replace(/"/g, '""') + '"';
        })
        .join(",");
    })
    .join("\n");
}

function fileMeta_(id) {
  var f = DriveApp.getFileById(id);
  return {
    id: id,
    name: f.getName(),
    mimeType: f.getMimeType(),
    size: f.getSize(),
  };
}

function reply_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON,
  );
}

/** Run this once from the editor (select testSetup -> Run) to grant permissions and check access. */
function testSetup() {
  var bde = "1Esi7wAV-Yyh8uasE2qmzaoArGMPsovQcvAXdog_XzQU";
  var csv = sheetCsv_(bde);
  Logger.log("BDE sheet rows: " + csv.split("\n").length);
}
