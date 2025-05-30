#!/bin/bash

# Load API key from .env file
source ./.notion_env  # Adjust if stored elsewhere

# Notion API version
NOTION_VERSION="2022-06-28"

# Check if a Page ID is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <notion_page_id>"
    exit 1
fi

PAGE_ID="$1"

# Notion API Endpoint
NOTION_API_URL="https://api.notion.com/v1/pages/$PAGE_ID"

# Make API request to get page details
response=$(curl -s -X GET "$NOTION_API_URL" \
    -H "Authorization: Bearer $NOTION_API_KEY" \
    -H "Notion-Version: $NOTION_VERSION" \
    -H "Content-Type: application/json")

# Print API response in a readable format
echo "$response" | jq .

