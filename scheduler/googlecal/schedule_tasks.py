#!/usr/bin/env python3
import subprocess
import json
import datetime
from dateutil import parser as dt_parser
from dateutil import tz
import re

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# Constants and Paths
TODO_SCRIPT_PATH = "/home/moneybot/scheduler/notion/api/generate_todo_list.sh"
SERVICE_ACCOUNT_FILE = "/home/moneybot/scheduler/googlecal/service.json"
CALENDAR_ID = "a252aec5fae47d681a372f6e37da3ccf0d9d352c3c8e31bde70b3b666a198da3@group.calendar.google.com"

# Time zone for MST
MST = tz.gettz("America/Phoenix")
# Maximum scheduling per day in hours
DAILY_MAX_HOURS = 6.5

# Google Calendar API setup
SCOPES = ["https://www.googleapis.com/auth/calendar"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build("calendar", "v3", credentials=creds)

# Utility: Return next weekday (skips Saturday=5, Sunday=6)
def get_next_weekday(date):
    while date.weekday() >= 5:
        date += datetime.timedelta(days=1)
    return date

# Parse the shell script output into a list of task dictionaries.
# Now expects: "priority | due | name (status) | build_time | url"
def parse_tasks(output):
    tasks = []
    lines = output.strip().split("\n")
    for line in lines:
        # Expecting format: "priority | due | name (status) | build_time | url"
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 5:
            continue  # skip malformed lines
        priority, due_str, name_status, build_time_str, url = parts

        # Extract task name and status
        match = re.match(r"(.+?)\s*\((.+?)\)$", name_status)
        if match:
            name = match.group(1).strip()
            status = match.group(2).strip()
        else:
            name = name_status
            status = ""

        # Parse build time: expected like "⏳ 2 hrs"
        build_time = 0.0
        m = re.search(r"(\d+(?:\.\d+)?)", build_time_str)
        if m:
            build_time = float(m.group(1))
        # If build time is 0, default to a 10-minute review (i.e. 1/6 hour)
        if build_time == 0:
            build_time = 1/6

        # Parse due date; if "No Due Date", set to a distant future date for sorting
        if due_str.lower() == "no due date":
            due_date = datetime.datetime.max.replace(tzinfo=MST)
        else:
            try:
                due_date = dt_parser.isoparse(due_str)
                if due_date.tzinfo is None:
                    due_date = due_date.replace(tzinfo=MST)
                else:
                    due_date = due_date.astimezone(MST)
            except Exception:
                due_date = datetime.datetime.max.replace(tzinfo=MST)

        tasks.append({
            "priority": priority,
            "due": due_date,
            "name": name,
            "status": status,
            "build_time": build_time,  # in hours
            "url": url
        })
    return tasks

# Priority mapping for sorting (highest first)
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

# Retrieve free slots for a given day (MST) within the work window 9:00-17:00, excluding lunch break (12-13)
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

    # Exclude lunch break: 12:00-13:00 MST.
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

# Inserts an event into Google Calendar; includes task URL in the event description.
def insert_calendar_event(task_name, start_time, end_time, url):
    event = {
        "summary": task_name,
        "description": f"Task URL: {url}",
        "start": {"dateTime": start_time.isoformat(), "timeZone": "America/Phoenix"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "America/Phoenix"},
    }
    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    if created_event.get("id"):
        print(f"✅ Scheduled '{task_name}' from {start_time} to {end_time}")
    else:
        print(f"❌ Failed to schedule '{task_name}'")
    return created_event

# Checks for future events related to a task. If the task is marked done, deletes any such events.
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
    matching_events = [
        event for event in future_events if event.get("summary", "") == task["name"]
    ]
    if matching_events:
        if task["status"].lower() == "done":
            for event in matching_events:
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

# Schedule tasks into available free slots
def schedule_tasks(tasks):
    current_day = get_next_weekday(datetime.datetime.now(tz=MST).date())
    daily_scheduled_hours = 0.0

    for task in tasks:
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
        if t["name"] not in unique_tasks:
            unique_tasks[t["name"]] = t
    tasks = list(unique_tasks.values())

    tasks = sort_tasks(tasks)
    print(f"📋 Retrieved and sorted {len(tasks)} tasks.")

    schedule_tasks(tasks)

if __name__ == "__main__":
    main()

