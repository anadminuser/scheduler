#!/bin/bash

# Load API key from local .env file
source ./.notion_env  # Ensure this path is correct

# Notion API version
NOTION_VERSION="2022-06-28"

# Default database ID (from your schema)
DATABASE_ID="6b493da2-f61e-4e6b-a6ae-0af71f753d33"

# Initialize empty filter object
FILTER_JSON=""

# Parse flags
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --title) FILTER_JSON='{"property": "Project name", "title": {"contains": "'"$2"'"}}'; shift ;;
        --owner) FILTER_JSON='{"property": "Owner", "people": {"contains": "'"$2"'"}}'; shift ;;
        --status) FILTER_JSON='{"property": "Status", "status": {"equals": "'"$2"'"}}'; shift ;;
        --priority) FILTER_JSON='{"property": "Priority", "select": {"equals": "'"$2"'"}}'; shift ;;
        --dates) FILTER_JSON='{"property": "Dates", "date": {"equals": "'"$2"'"}}'; shift ;;
        --summary) FILTER_JSON='{"property": "Summary", "rich_text": {"contains": "'"$2"'"}}'; shift ;;
        --blocking) FILTER_JSON='{"property": "Is Blocking", "relation": {"contains": "'"$2"'"}}'; shift ;;
        --blocked_by) FILTER_JSON='{"property": "Blocked By", "relation": {"contains": "'"$2"'"}}'; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# Ensure FILTER_JSON is valid or use an empty object
if [[ -z "$FILTER_JSON" ]]; then
    QUERY_JSON="{}"
else
    QUERY_JSON="{\"filter\": $FILTER_JSON}"
fi

# Notion API Endpoint to query database
NOTION_API_URL="https://api.notion.com/v1/databases/$DATABASE_ID/query"

# Make API request
response=$(curl -s -X POST "$NOTION_API_URL" \
    -H "Authorization: Bearer $NOTION_API_KEY" \
    -H "Notion-Version: $NOTION_VERSION" \
    -H "Content-Type: application/json" \
    --data "$QUERY_JSON")

# Print API response in a readable format
echo "$response" | jq .

