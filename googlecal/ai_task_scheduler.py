#!/usr/bin/env python3
import os
import json
import datetime
from dateutil import parser as dt_parser
from dateutil import tz
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from chatgpt.ai_analyzer import analyze_tasks  # Import from new module

# --- Configuration and Constants ---
TODO_SCRIPT_PATH = "/home/moneybot/scheduler/notion/api/generate_todo_list.sh"
SERVICE_ACCOUNT_FILE = "/home/moneybot/scheduler/googlecal/service.json"
CALENDAR_ID = "a252aec5fae47d681a372f6e37da3ccf0d9d352c3c8e31bde70b3b666a198da3@group.calendar.google.com"

# Time zone for MST
MST = tz.gettz("America/Phoenix")

# Google Calendar API setup
SCOPES = ["https://www.googleapis.com/auth/calendar"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build("calendar", "v3", credentials=creds)

# --- Helper Functions ---

def fetch_calendar_events():
    """
    Retrieves upcoming calendar events from now until 7 days ahead.
    Returns a list of events with summary, start, and end.
    """
    now = datetime.datetime.now(tz=MST)
    end_time = now + datetime.timedelta(days=7)
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now.isoformat(),
        timeMax=end_time.isoformat(),
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    events = events_result.get("items", [])
    formatted_events = []
    for event in events:
        summary = event.get("summary", "No Title")
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        formatted_events.append({"summary": summary, "start": start, "end": end})
    return formatted_events

# --- Example Usage ---
if __name__ == "__main__":
    # Example tasks from Notion (expected format)
    sample_tasks = [
        {
            "priority": "🔹 High",
            "due": "2025-02-18T00:00:00-07:00",
            "name": "Create task not complete logic/reschedule",
            "status": "In progress",
            "build_time": 2.0,
            "url": "https://www.notion.so/Create-task-not-complete-logic-reschedule-19a5401dccdb80119670e1b7064f3619"
        },
        {
            "priority": "🔹 Medium",
            "due": "2025-02-15T00:00:00-07:00",
            "name": "Refine how tasks get priority",
            "status": "Done",
            "build_time": 0.16667,
            "url": "https://www.notion.so/Refine-how-tasks-get-priority-19a5401dccdb8044bd7cc45909ff99c9"
        }
    ]
    
    print("Original tasks:")
    print(json.dumps(sample_tasks, indent=2))
    
    # Fetch calendar events and analyze tasks
    calendar_events = fetch_calendar_events()
    analyzed_tasks = analyze_tasks(sample_tasks, calendar_events)
    print("\nAnalyzed tasks:")
    print(json.dumps(analyzed_tasks, indent=2))