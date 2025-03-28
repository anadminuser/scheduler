from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import datetime

# Load credentials
SCOPES = ["https://www.googleapis.com/auth/calendar"]
SERVICE_ACCOUNT_FILE = "./service.json"

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build("calendar", "v3", credentials=creds)

# Define working hours
WORK_HOURS_START = 9
WORK_HOURS_END = 17

# Get today's date
now = datetime.datetime.utcnow()
start_of_day = now.replace(hour=WORK_HOURS_START, minute=0, second=0).isoformat() + "Z"
end_of_day = now.replace(hour=WORK_HOURS_END, minute=0, second=0).isoformat() + "Z"

# Query events for today
events_result = service.events().list(
    calendarId="primary",
    timeMin=start_of_day,
    timeMax=end_of_day,
    singleEvents=True,
    orderBy="startTime",
).execute()
events = events_result.get("items", [])

# Find open slots
free_slots = []
last_end_time = start_of_day

for event in events:
    start = event["start"].get("dateTime", event["start"].get("date"))
    end = event["end"].get("dateTime", event["end"].get("date"))

    if last_end_time < start:
        free_slots.append({"start": last_end_time, "end": start})
    
    last_end_time = end

# Check if there is time after the last event
if last_end_time < end_of_day:
    free_slots.append({"start": last_end_time, "end": end_of_day})

# Print free slots
print("Available Slots:")
for slot in free_slots:
    print(f"From {slot['start']} to {slot['end']}")

