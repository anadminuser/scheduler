#!/bin/bash

# Get all tasks and format them
TASKS=$(/home/moneybot/scheduler/notion/api/query_notion_database.sh | jq -r '
    .results[] |
    {
        name: (.properties["Project name"].title[0].plain_text // "Untitled"),
        priority: (.properties["Priority"].select.name // "No Priority"),
        status: (.properties["Status"].status.name // "No Status"),
        due: (.properties["Dates"].date.start // "No Due Date"),
        build_time: (.properties["Total Build Time"].number // 0),
	url: (.url)
    }' | jq -s 'sort_by(.priority, .due)')

# Print formatted list
#echo "Priority To-Do List:"
echo "$TASKS" | jq -r '.[] | "\(.priority) | \(.due) | \(.name) (\(.status)) | \(.build_time) hrs | \(.url)"'

