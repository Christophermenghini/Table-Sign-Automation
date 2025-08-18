from __future__ import annotations
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ========= CONFIG =========
TEMPLATE_DOC_ID = "1W6gFO2zL-qDulhsT2O1uSRP3ct3DNpxyuMXRLb1lLDQ"  # <-- Template Google Doc ID
SILC_CAL_ID     = "cqoqsrchl91slfels587k54k9g@group.calendar.google.com"  # SILC Café calendar
TIMEZONE        = "America/Phoenix"

NUM_TABLES          = 8
EVENTS_PER_TABLE    = 3   # 3 rows per table (max 3 events shown)
DATE_OFFSET_DAYS    = 3   # 0=today, 1=tomorrow, etc.

OUTPUT_PREFIX       = "SILC Cafe Signs - "  # final: PREFIX + YYYY-MM-DD
TARGET_FOLDER_ID    = None  # put copies in a specific Drive folder ID (or None)

# OPTIONAL: future routing — map regex (case-insensitive) -> table number (1..8).
# If non-empty, matched events will be assigned to that table (up to 3 per table).
# Unmatched events can still be duplicated to all tables (see DUPLICATE_TO_ALL_WHEN_ROUTING).
TABLE_ROUTING: Dict[str, int] = {
    # r"conversation hour": 1,
    # r"spanish": 2,
    # r"french": 3,
}
DUPLICATE_TO_ALL_WHEN_ROUTING = True  # True = also show routed events on all tables
# =========================

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.readonly",  # <-- add this
    "https://www.googleapis.com/auth/drive.file",
]


def get_creds():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError("credentials.json not found next to this script.")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return creds

def fetch_events_for_day(creds, calendar_id: str, tz_name: str, day_offset: int, max_needed: int) -> (List[Dict], datetime.date):
    """Fetch enough events for the day (sorted), return list of dicts with title/start/end."""
    cal = build("calendar", "v3", credentials=creds)
    tz = ZoneInfo(tz_name)

    target_date = datetime.now(tz).date() + timedelta(days=day_offset)
    start_local = datetime.combine(target_date, datetime.min.time(), tz)
    end_local   = start_local + timedelta(days=1)

    resp = cal.events().list(
        calendarId=calendar_id,
        timeMin=start_local.isoformat(),
        timeMax=end_local.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=max(200, max_needed)
    ).execute()

    items = resp.get("items", [])
    events: List[Dict] = []
    for e in items:
        title = (e.get("summary") or "").strip() or "(No Title)"

        # Normalize start/end (dateTime or all-day date)
        start_s = e["start"].get("dateTime") or (e["start"].get("date") + "T00:00:00")
        end_s   = e["end"].get("dateTime")   or (e["end"].get("date")   + "T23:59:59")

        # Convert to local tz; support 'Z'
        start_dt = datetime.fromisoformat(start_s.replace("Z", "+00:00")).astimezone(tz)
        end_dt   = datetime.fromisoformat(end_s.replace("Z", "+00:00")).astimezone(tz)

        # 12-hour format; for all-day, leave blank (change to "All day" if you prefer)
        if e["start"].get("date"):
            start_str, end_str = "", ""
        else:
            # %-I works on mac/Linux; on Windows use %#I
            start_str = start_dt.strftime("%-I:%M %p")
            end_str   = end_dt.strftime("%-I:%M %p")

        events.append({"title": title, "start": start_str, "end": end_str})

        if len(events) >= max_needed:
            break

    return events, target_date

def distribute_for_today(events: List[Dict]) -> List[List[Dict]]:
    """
    TODAY'S MODE: duplicate the same top 1–3 events across all 8 tables.
    FUTURE: if TABLE_ROUTING is set, route matching events to specific tables (up to 3 each).
    """
    top = events[:EVENTS_PER_TABLE]

    if not TABLE_ROUTING:
        # Simple: same 1–3 events for every table
        return [top.copy() for _ in range(NUM_TABLES)]

    # Future routing mode
    routed: List[List[Dict]] = [[] for _ in range(NUM_TABLES)]  # index 0..7 for tables 1..8
    unmatched: List[Dict] = []

    for ev in events:
        placed = False
        for pattern, table_num in TABLE_ROUTING.items():
            if re.search(pattern, ev["title"], flags=re.IGNORECASE):
                idx = max(1, min(NUM_TABLES, table_num)) - 1
                if len(routed[idx]) < EVENTS_PER_TABLE:
                    routed[idx].append(ev)
                    placed = True
                break
        if not placed:
            unmatched.append(ev)

    if DUPLICATE_TO_ALL_WHEN_ROUTING:
        # Every table shows the same first up-to-3 events (like today’s mode)
        base = events[:EVENTS_PER_TABLE]
        routed = [base.copy() for _ in range(NUM_TABLES)]

    # Ensure each table has at most EVENTS_PER_TABLE items (already ensured)
    return routed

def copy_template(creds, template_id: str, new_title: str) -> str:
    drive = build("drive", "v3", credentials=creds)
    body = {"name": new_title}
    if TARGET_FOLDER_ID:
        body["parents"] = [TARGET_FOLDER_ID]
    new_file = drive.files().copy(fileId=template_id, body=body).execute()
    return new_file["id"]

def fill_placeholders(creds, doc_id: str, date_str: str, tables: List[List[Dict]]):
    docs = build("docs", "v1", credentials=creds)

    mapping = {"{{DATE}}": date_str}

    for x in range(1, NUM_TABLES + 1):
        rows = tables[x - 1] if x - 1 < len(tables) else []
        for y in range(1, EVENTS_PER_TABLE + 1):
            if y - 1 < len(rows):
                ev = rows[y - 1]
                mapping[f"{{{{EVENT{x}{y}}}}}"] = ev["title"]
                mapping[f"{{{{START{x}{y}}}}}"] = ev["start"]
                mapping[f"{{{{END{x}{y}}}}}"]   = ev["end"]
            else:
                mapping[f"{{{{EVENT{x}{y}}}}}"] = ""
                mapping[f"{{{{START{x}{y}}}}}"] = ""
                mapping[f"{{{{END{x}{y}}}}}"]   = ""

    requests = [{
        "replaceAllText": {
            "containsText": {"text": ph, "matchCase": True},
            "replaceText": val
        }
    } for ph, val in mapping.items()]

    docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

def try_delete_yesterdays_copy(creds, prefix: str, tz_name: str):
    drive = build("drive", "v3", credentials=creds)
    tz = ZoneInfo(tz_name)
    yest = (datetime.now(tz) - timedelta(days=1)).date().isoformat()
    target_name = f"{prefix}{yest}"

    q = (
        "mimeType='application/vnd.google-apps.document' "
        f"and name='{target_name}' and trashed=false"
    )
    resp = drive.files().list(q=q, fields="files(id, name)", spaces="drive").execute()
    for f in resp.get("files", []):
        try:
            drive.files().delete(fileId=f["id"]).execute()
            print(f"Deleted yesterday's doc: {f['name']}")
        except Exception as ex:
            print(f"Could not delete {f['name']}: {ex}")

def main():
    creds = get_creds()

    # We only need up to 3 events for today's duplication, but fetch a few extra just in case
    events, target_date = fetch_events_for_day(
        creds, SILC_CAL_ID, TIMEZONE, DATE_OFFSET_DAYS, max_needed=24
    )

    tables = distribute_for_today(events)

    tz = ZoneInfo(TIMEZONE)
    date_header = datetime.combine(target_date, datetime.min.time(), tz).strftime("%A, %B %-d, %Y")
    date_for_filename = target_date.isoformat()  # YYYY-MM-DD

    new_title = f"{OUTPUT_PREFIX}{date_for_filename}"
    new_doc_id = copy_template(creds, TEMPLATE_DOC_ID, new_title)
    print(f"Created today's doc: {new_title} (id: {new_doc_id})")

    fill_placeholders(creds, new_doc_id, date_header, tables)
    print(f"Filled placeholders. Top {min(len(events), 3)} event(s) duplicated across all tables.")

    try_delete_yesterdays_copy(creds, OUTPUT_PREFIX, TIMEZONE)

if __name__ == "__main__":
    main()
