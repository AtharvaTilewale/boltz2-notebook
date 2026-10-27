/**
 * Receiver for Boltz2-Notebook usage reports (docs/TELEMETRY.md).
 *
 * It stores what it is sent in a Google Sheet that only you own, and it can not read it: every report is sealed
 * with your PUBLIC key inside the user's runtime, so the sheet holds ciphertext only. Open it with
 * tools/telemetry_read.py and your private key.
 *
 * Deploy: Extensions > Apps Script in the Sheet, paste this file, Deploy > New deployment > Web app,
 * "Execute as: Me", "Who has access: Anyone" (the notebooks post without logging in). Copy the web app URL into
 * boltz2nb/telemetry_config.py as ENDPOINT. The script never sees the sender's address or any account.
 */
const SHEET_NAME = 'reports';
const MAX_CHARS = 40000;      // a report is far smaller; a Sheets cell holds 50000 characters

function doPost(e) {
  const p = e && e.parameter ? e.parameter.p : null;
  const v = e && e.parameter ? e.parameter.v : null;
  if (v !== '1' || !p || p.length > MAX_CHARS || !/^[A-Za-z0-9+\/=]+$/.test(p)) {
    return reply('rejected');
  }
  const book = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = book.getSheetByName(SHEET_NAME) || book.insertSheet(SHEET_NAME);
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['received_utc', 'schema', 'sealed_report']);
  }
  // the prefix keeps Sheets from reading a value that starts with = or + as a formula
  sheet.appendRow([new Date().toISOString(), v, 'sealed:' + p]);
  return reply('ok');
}

function doGet() {
  return reply('Boltz2-Notebook usage collector (write-only)');
}

function reply(text) {
  return ContentService.createTextOutput(text);
}
