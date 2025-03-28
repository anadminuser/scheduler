#!/bin/bash

# Load API key from local .env file
source ./.notion_env  # Ensure this path is correct

# Notion API version
NOTION_VERSION="2022-06-28"

# Default database ID (from your schema)
DATABASE_ID="6b493da2-f61e-4e6b-a6ae-0af71f753d33"

# Initialize an array for filters
FILTERS=()

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --title) FILTERS+=('{"property": "Project name", "title": {"contains": "'"$2"'"}}'); shift ;;
        --owner) FILTERS+=('{"property": "Owner", "people": {"contains": "'"$2"'"}}'); shift ;;
        --status) FILTERS+=('{"property": "Status", "status": {"equals": "'"$2"'"}}'); shift ;;
        --not-status) FILTERS+=('{"property": "Status", "status": {"does_not_equal": "'"$2"'"}}'); shift ;;
        --priority) FILTERS+=('{"property": "Priority", "select": {"equals": "'"$2"'"}}'); shift ;;
        --dates) FILTERS+=('{"property": "Dates", "date": {"equals": "'"$2"'"}}'); shift ;;
        --summary) FILTERS+=('{"property": "Summary", "rich_text": {"contains": "'"$2"'"}}'); shift ;;
        --blocking) FILTERS+=('{"property": "Is Blocking", "relation": {"contains": "'"$2"'"}}'); shift ;;
        --blocked_by) FILTERS+=('{"property": "Blocked By", "relation": {"contains": "'"$2"'"}}'); shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# Combine filters if provided
if [[ ${#FILTERS[@]} -gt 1 ]]; then
    QUERY_JSON="{\"filter\": {\"and\": [$(IFS=,; echo "${FILTERS[*]}") ]}}"
elif [[ ${#FILTERS[@]} -eq 1 ]]; then
    QUERY_JSON="{\"filter\": ${FILTERS[0]}}"
else
    QUERY_JSON="{}"
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
