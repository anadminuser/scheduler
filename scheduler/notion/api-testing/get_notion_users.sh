#!/bin/bash

# Load API key from local .env file
source ./.notion_env  # Ensure this path is correct

# Notion API version
NOTION_VERSION="2022-06-28"

# Notion API Endpoint to retrieve users (members)
NOTION_API_URL="https://api.notion.com/v1/users"

# Make API request to get workspace members
response=$(curl -s -X GET "$NOTION_API_URL" \
    -H "Authorization: Bearer $NOTION_API_KEY" \
    -H "Notion-Version: $NOTION_VERSION" \
    -H "Content-Type: application/json")

# Print API response in a readable format
echo "$response" | jq .

