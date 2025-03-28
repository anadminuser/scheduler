#!/usr/bin/env python3
import os
import json
import datetime
from dateutil import tz
from openai import OpenAI

# Time zone for MST
MST = tz.gettz("America/Phoenix")

# OpenAI client setup
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or "your-api-key-here")

def sanitize_json_output(s):
    """Fix incomplete JSON by ensuring it’s a valid array."""
    s = s.strip()
    if not s.startswith("["):
        s = "[" + s
    if not s.endswith("]"):
        last_brace = s.rfind("}")
        if last_brace != -1:
            s = s[:last_brace + 1] + "]"
        else:
            s += "]"
    return s

def analyze_tasks(tasks, calendar_events):
    """Analyze tasks with ChatGPT, adding useful fields."""
    tasks_serializable = []
    for t in tasks:
        t_copy = t.copy()
        if isinstance(t_copy.get("due"), datetime.datetime):
            t_copy["due"] = t_copy["due"].isoformat()
        tasks_serializable.append(t_copy)
    
    tasks_json = json.dumps(tasks_serializable, indent=2)
    calendar_events_json = json.dumps(calendar_events, indent=2)

    # Count events per day over the next 7 days
    now = datetime.datetime.now(tz=MST).date()
    event_counts = {now + datetime.timedelta(days=i): 0 for i in range(7)}
    for event in calendar_events:
        start_str = event.get("start")
        if start_str:
            try:
                event_date = datetime.datetime.fromisoformat(start_str).astimezone(MST).date()
                if event_date in event_counts:
                    event_counts[event_date] += 1
            except ValueError:
                continue
    event_count_str = "\n".join([f"{date}: {count} events" for date, count in event_counts.items()])
    min_event_date = min(event_counts, key=event_counts.get)
    min_event_count = event_counts[min_event_date]
    
    prompt = f"""
You are an AI scheduling assistant with expertise in project management and technical development. I provide a list of tasks in JSON format with:
- priority (string, e.g., "High", "Medium", "No Priority")
- due (ISO datetime string or "No Due Date")
- name (string, detailed task info)
- status (string, e.g., "In progress", "Planning", "Backlog")
- build_time (float, hours)
- url (string)

Here are my upcoming calendar events for the next 7 days:
{calendar_events_json}

Event counts per day:
{event_count_str}

The date with the fewest events is {min_event_date} with {min_event_count} events.

For each task:
1. Analyze the "name" and "description" (if present) to understand the task’s purpose and requirements.
2. Set a realistic "build_time" in hours:
   - If current build_time is 0 or 0.16667 (10 min), assign a new value based on complexity:
     - "Research" tasks (e.g., "Investigate"): 2-4 hours (default 3 if unsure).
     - "Design" tasks (e.g., "Create"): 3-6 hours (default 4 if unsure).
     - "Focus" tasks (e.g., reviews, fixes): 0.5-2 hours (default 1 if unsure).
   - If build_time is already set (e.g., 10), keep it unless the description clearly indicates it’s inaccurate.
   - For all non-"Done" tasks, ensure build_time is NEVER 0—assign a minimum of 0.5 hours if no other estimate fits.
3. Assign a "task_type" as "research", "design", or "focus" (e.g., "Investigate" → "research", "Create" → "design", else "focus").
4. Provide a "suggested_solution" with a specific, actionable next step tailored to the task. Include precise tools, methods, or resources (e.g., "Implement a decision tree with scikit-learn’s DecisionTreeClassifier"). Avoid vague phrases like "start researching" or "consider using"—give a clear action or reference.
5. Respect due dates and priority for timing (e.g., urgent tasks suggest immediate steps).
6. Suggest grouping heavy focus tasks on days with fewer events (e.g., "Schedule on {min_event_date} with {min_event_count} events" if it’s a focus task).

Return a valid JSON array (start with '[', end with ']') with all original fields plus "task_type" and "suggested_solution". Ensure complete objects—no partial outputs.

Input:
{tasks_json}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an AI scheduling assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000
        )
    except Exception as e:
        print("Error calling OpenAI API:", e)
        return tasks

    answer = response.choices[0].message.content.strip()
    answer = sanitize_json_output(answer)
    try:
        updated_tasks = json.loads(answer)
        # Fallback: Ensure no non-"Done" task has build_time of 0
        for task in updated_tasks:
            if task["status"].lower() != "done" and task["build_time"] <= 0:
                if task["task_type"] == "research":
                    task["build_time"] = 3
                elif task["task_type"] == "design":
                    task["build_time"] = 4
                else:  # focus
                    task["build_time"] = 1
        return updated_tasks
    except Exception as e:
        print("Error parsing AI response:", e)
        print("AI response was:", answer)
        return tasks

if __name__ == "__main__":
    sample_tasks = [
        {
            "priority": "High",
            "due": "2025-02-18T00:00:00-07:00",
            "name": "Create task not complete logic/reschedule",
            "status": "In progress",
            "build_time": 2.0,
            "url": "https://www.notion.so/Create-task-not-complete-logic-reschedule-19a5401dccdb80119670e1b7064f3619"
        }
    ]
    sample_events = [
        {"summary": "Meeting", "start": "2025-02-17T10:00:00-07:00", "end": "2025-02-17T11:00:00-07:00"}
    ]
    analyzed = analyze_tasks(sample_tasks, sample_events)
    print(json.dumps(analyzed, indent=2))