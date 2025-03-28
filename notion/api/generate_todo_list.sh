#!/bin/bash

# Get all tasks and format them as a JSON array
TASKS=$(./scheduler/notion/api/query_notion_database.sh | jq -r '
    .results[] |
    {
        name: (.properties["Project name"].title[0].plain_text // "Untitled"),
        priority: (.properties["Priority"].select.name // "No Priority"),
        status: (.properties["Status"].status.name // "No Status"),
        due: (.properties["Dates"].date.start // "No Due Date"),
        build_time: (.properties["Total Build Time"].number // 0),
        url: (.url),
        description: (.properties["Description"].rich_text[0].plain_text // ""),
        tags: ((.properties["Tags"].multi_select // []) | map(.name) | join(", ")),
        dependencies: ((.properties["Dependencies"].relation // []) | map(.id) | join(", ")),
        complexity: (.properties["Complexity"].select.name // "Unknown"),
        assigned_to: ((.properties["Assigned To"].people // []) | map(.name) | join(", "))
    }' | jq -s 'sort_by(.priority, .due)')

# Output the raw JSON array for use by other scripts
echo "$TASKS"

