#!/usr/bin/env python3
import subprocess
import json
import datetime
from dateutil import parser as dt_parser
from dateutil import tz
import re

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# --- Configuration and Paths ---
TODO_SCRIPT_PATH = "/home/moneybot/scheduler/notion/api/generate_todo_list.sh"
SERVICE_ACCOUNT_FILE = "/home/moneybot/scheduler/googlecal/service.json"
CALENDAR_ID = "a252aec5fae47d681a372f6e37da3ccf0d9d352c3c8e31bde70b3b666a198da3@group.calendar.google.com"

# Global flags:
DRY_RUN = True             # Set to True for a dry run (no actual calendar changes)
USE_AI_MODE = True         # Set to True to run tasks through AI analysis

# Time zone for MST
MST = tz.gettz("America/Phoenix")
# Maximum scheduling per day in hours
DAILY_MAX_HOURS = 6.5

# Google Calendar API setup
SCOPES = ["https://www.googleapis.com/auth/calendar"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build("calendar", "v3", credentials=creds)

# --- Helper Functions ---

def get_next_weekday(date):
    while date.weekday() >= 5:
        date += datetime.timedelta(days=1)
    return date

def parse_tasks(output):
    """
    Updated to simply parse raw JSON output from generate_todo_list.sh.
    """
    try:
        tasks = json.loads(output)
        return tasks
    except Exception as e:
        print("Error parsing tasks:", e)
        return []

PRIORITY_MAP = {
    "🔹 High": 3,
    "High": 3,
    "🔹 Medium": 2,
    "Medium": 2,
    "🔹 No Priority": 1,
    "No Priority": 1
}

def sort_tasks(tasks):
    def sort_key(task):
        prio = PRIORITY_MAP.get(task["priority"], 0)
        return (-prio, task["due"])
    return sorted(tasks, key=sort_key)

def get_free_slots_for_day(day_date):
    start_of_day = datetime.datetime.combine(day_date, datetime.time(9, 0)).replace(tzinfo=MST)
    end_of_day = datetime.datetime.combine(day_date, datetime.time(17, 0)).replace(tzinfo=MST)

    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_of_day.isoformat(),
        timeMax=end_of_day.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    events = events_result.get("items", [])
    print(f"🔍 Retrieved {len(events)} existing events for {day_date.isoformat()}.")

    free_slots = []
    last_end = start_of_day
    for event in events:
        start_str = event["start"].get("dateTime", event["start"].get("date"))
        end_str = event["end"].get("dateTime", event["end"].get("date"))
        try:
            event_start = dt_parser.isoparse(start_str).astimezone(MST)
            event_end = dt_parser.isoparse(end_str).astimezone(MST)
        except Exception as e:
            print(f"❌ Error parsing event times: {e}")
            continue

        if last_end < event_start:
            free_slots.append({"start": last_end, "end": event_start})
        last_end = max(last_end, event_end)

    if last_end < end_of_day:
        free_slots.append({"start": last_end, "end": end_of_day})

    lunch_start = datetime.datetime.combine(day_date, datetime.time(12, 0)).replace(tzinfo=MST)
    lunch_end = datetime.datetime.combine(day_date, datetime.time(13, 0)).replace(tzinfo=MST)
    free_slots_adjusted = []
    for slot in free_slots:
        if slot["end"] <= lunch_start or slot["start"] >= lunch_end:
            free_slots_adjusted.append(slot)
        else:
            if slot["start"] < lunch_start:
                free_slots_adjusted.append({"start": slot["start"], "end": lunch_start})
            if slot["end"] > lunch_end:
                free_slots_adjusted.append({"start": lunch_end, "end": slot["end"]})
    return free_slots_adjusted

def insert_calendar_event(task_name, start_time, end_time, url):
    event = {
        "summary": task_name,
        "description": f"Task URL: {url}",
        "start": {"dateTime": start_time.isoformat(), "timeZone": "America/Phoenix"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "America/Phoenix"},
    }
    if DRY_RUN:
        print(f"DRY RUN: Would schedule '{task_name}' from {start_time} to {end_time} with URL: {url}")
        return {"id": "dry-run", "summary": task_name}
    else:
        created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        if created_event.get("id"):
            print(f"✅ Scheduled '{task_name}' from {start_time} to {end_time}")
        else:
            print(f"❌ Failed to schedule '{task_name}'")
        return created_event

def handle_existing_events_for_task(task):
    now_mst = datetime.datetime.now(tz=MST)
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now_mst.isoformat(),
        singleEvents=True,
        q=task["name"],
        orderBy="startTime"
    ).execute()
    future_events = events_result.get("items", [])
    matching_events = [event for event in future_events if event.get("summary", "") == task["name"]]
    if matching_events:
        if task["status"].lower() == "done":
            for event in matching_events:
                if DRY_RUN:
                    print(f"DRY RUN: Would delete event '{event['id']}' for task '{task['name']}'.")
                else:
                    try:
                        service.events().delete(calendarId=CALENDAR_ID, eventId=event["id"]).execute()
                        print(f"🗑 Removed scheduled event for completed task '{task['name']}'.")
                    except Exception as e:
                        print(f"❌ Error deleting event {event['id']}: {e}")
            return True
        else:
            print(f"ℹ️ Task '{task['name']}' is already scheduled in the future. Skipping.")
            return True
    return False

def schedule_tasks(tasks):
    current_day = get_next_weekday(datetime.datetime.now(tz=MST).date())
    daily_scheduled_hours = 0.0

    # Group tasks by type if provided by AI
    tasks_by_type = {}
    for task in tasks:
        if task["status"].lower() == "done":  # Skip Done tasks
            continue
        task_type = task.get("task_type", "focus")  # Default to "focus"
        tasks_by_type.setdefault(task_type, []).append(task)

    for task_type, type_tasks in tasks_by_type.items():
        print(f"\n📋 Scheduling {task_type} tasks")
        for task in type_tasks:
            if handle_existing_events_for_task(task):
                continue

            remaining_time = task["build_time"]
            print(f"\n📋 Scheduling task: {task['name']} (Total: {remaining_time} hrs, Status: {task['status']})")
            while remaining_time > 0:
                if daily_scheduled_hours >= DAILY_MAX_HOURS:
                    print(f"ℹ️ Daily limit reached ({DAILY_MAX_HOURS} hrs). Moving to next day.")
                    current_day = get_next_weekday(current_day + datetime.timedelta(days=1))
                    daily_scheduled_hours = 0.0

                free_slots = get_free_slots_for_day(current_day)
                now_mst = datetime.datetime.now(tz=MST)
                if current_day == now_mst.date():
                    free_slots = [s for s in free_slots if s["end"] > now_mst]
                    if free_slots and free_slots[0]["start"] < now_mst:
                        free_slots[0]["start"] = now_mst

                if not free_slots:
                    print(f"⚠️ No free slots on {current_day}. Moving to next day.")
                    current_day = get_next_weekday(current_day + datetime.timedelta(days=1))
                    daily_scheduled_hours = 0.0
                    continue

                slot_found = False
                for slot in free_slots:
                    slot_start = slot["start"]
                    slot_end = slot["end"]
                    available_slot_duration = (slot_end - slot_start).total_seconds() / 3600.0
                    available_slot_duration = min(available_slot_duration, DAILY_MAX_HOURS - daily_scheduled_hours)
                    if available_slot_duration <= 0:
                        continue

                    scheduled_duration = min(remaining_time, available_slot_duration)
                    event_end = slot_start + datetime.timedelta(hours=scheduled_duration)
                    insert_calendar_event(task["name"], slot_start, event_end, task["url"])
                    daily_scheduled_hours += scheduled_duration
                    remaining_time -= scheduled_duration
                    slot_found = True
                    break

                if not slot_found:
                    print(f"⚠️ No suitable slot found on {current_day}. Moving to next day.")
                    current_day = get_next_weekday(current_day + datetime.timedelta(days=1))
                    daily_scheduled_hours = 0.0

def main():
    try:
        task_output = subprocess.run([TODO_SCRIPT_PATH], capture_output=True, text=True, check=True)
        raw_tasks = parse_tasks(task_output.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running task script: {e}")
        return

    if not raw_tasks:
        print("ℹ️ No tasks retrieved.")
        return

    unique_tasks = {}
    for t in raw_tasks:
        if t["name"] not in unique_tasks and t["status"].lower() !="done":
            unique_tasks[t["name"]] = t
            print(t["name"])
    tasks = list(unique_tasks.values())

    tasks = sort_tasks(tasks)
    print(f"📋 Retrieved and sorted {len(tasks)} tasks.")

    # Filter out "Done" tasks before AI analysis
    active_tasks = [task for task in tasks if task["status"].lower() != "done"]

    # If AI mode is enabled, process only active tasks
    if USE_AI_MODE:
        try:
            from chatgpt.ai_analyzer import analyze_tasks
            from ai_task_scheduler import fetch_calendar_events
            calendar_events = fetch_calendar_events()
            if active_tasks:  # Only call AI if there are active tasks
                analyzed_tasks = analyze_tasks(active_tasks, calendar_events)
                print("🤖 AI analysis complete. Updated tasks:")
                print(json.dumps(analyzed_tasks, indent=2))
            else:
                analyzed_tasks = []
                print("ℹ️ No active tasks to analyze.")
        except Exception as e:
            print(f"❌ Error running AI analysis: {e}")
            analyzed_tasks = active_tasks  # Fallback to unanalyzed active tasks

    schedule_tasks(analyzed_tasks)

if __name__ == "__main__":
    main()

