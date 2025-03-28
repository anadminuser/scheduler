#!/bin/bash

# Load API key from .env file
source ./.notion_env  # Adjust path if needed

# Notion API version
NOTION_VERSION="2022-06-28"

# Notion API Endpoint
NOTION_API_URL="https://api.notion.com/v1/search"

# Make API request to list pages (or modify as needed)
response=$(curl -s -X POST "$NOTION_API_URL" \
    -H "Authorization: Bearer $NOTION_API_KEY" \
    -H "Notion-Version: $NOTION_VERSION" \
    -H "Content-Type: application/json" \
    --data '{
        "filter": {
            "value": "page",
            "property": "object"
        }
    }')

# Print API response
echo "$response"

