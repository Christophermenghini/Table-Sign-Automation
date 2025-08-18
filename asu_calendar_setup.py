from __future__ import annotations
import argparse
import os
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Read-only to start; upgrade to "https://www.googleapis.com/auth/calendar"
# later if you need create/update/delete.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

def get_service():
    """
    Builds an authenticated Calendar API client.
    - Expects credentials.json in the same folder.
    - Saves token.json after first login (ASU sign-in).
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError(
                    "credentials.json not found. Put your OAuth client file next to this script."
                )
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            # Opens a browser; sign in with your ASU account.
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def list_calendars():
    """Print all calendars you can see, with their IDs (useful for shared job calendars)."""
    service = get_service()
    print("\n== Your calendars (name  —  ID) ==\n")
    page_token = None
    count = 0
    while True:
        resp = service.calendarList().list(pageToken=page_token, minAccessRole="reader").execute()
        for cal in resp.get("items", []):
            count += 1
            summary = cal.get("summary", "(no title)")
            cal_id = cal.get("id", "")
            access = cal.get("accessRole", "")
            print(f"- {summary}  —  {cal_id}  (access: {access})")
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    if count == 0:
        print("No calendars found.")

def list_upcoming_events(calendar_id: str, max_results: int = 10, days_ahead: int = 30):
    """List upcoming events from a specific calendar."""
    service = get_service()
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days_ahead)).isoformat()

    resp = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = resp.get("items", [])
    print(f"\n== Upcoming events on {calendar_id} (next {days_ahead} days, up to {max_results}) ==\n")
    if not events:
        print("No upcoming events.")
        return

    for e in events:
        start = e["start"].get("dateTime", e["start"].get("date"))
        end = e["end"].get("dateTime", e["end"].get("date"))
        title = e.get("summary", "(no title)")
        print(f"{start}  →  {end}   |   {title}")

def main():
    parser = argparse.ArgumentParser(description="ASU Google Calendar: first-run + list events")
    parser.add_argument("--calendar", "-c", help="Calendar ID (use 'primary' or a shared calendar ID)")
    parser.add_argument("--max", type=int, default=10, help="Max events to list (default: 10)")
    parser.add_argument("--days", type=int, default=30, help="Days ahead to search (default: 30)")
    args = parser.parse_args()

    # Always show calendars first (helps you grab the shared calendar ID).
    list_calendars()

    # If a calendar was provided, show its upcoming events.
    if args.calendar:
        list_upcoming_events(args.calendar, max_results=args.max, days_ahead=args.days)
    else:
        print("\nTip: To list events, rerun with --calendar <ID> (use 'primary' or one printed above).")

if __name__ == "__main__":
    main()
