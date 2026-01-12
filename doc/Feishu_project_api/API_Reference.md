# Feishu Project API Reference

This document provides a complete reference for the Feishu Project Open API, derived from the official Go/Java SDK specifications. Since there is currently no official Python SDK, this guide includes Python examples using standard HTTP libraries.

## 1. Overview

### Base URL
```
https://project.feishu.cn
```

### Authentication
All API requests require specific headers for authentication and context.

| Header | Description | Required | Note |
|--------|-------------|----------|------|
| `X-PLUGIN-TOKEN` | Access Token (User Plugin Token) | **Yes** | Obtained via auth flow. |
| `X-USER-KEY` | User ID | **Yes** | Identifies the operator. |
| `Content-Type` | Content Type | **Yes** | Must be `application/json`. |

## 2. Work Item API

### 2.1 Create Work Item
Create a new work item in a specific project.

- **Method**: `POST`
- **Path**: `/open_api/:project_key/work_item/create`
- **URL Params**:
  - `project_key`: The unique key of the project.

**Request Body (JSON):**
```json
{
  "work_item_type_key": "task",  // Required: "task", "bug", "requirement", etc.
  "template_id": 12345,          // Optional: Template ID
  "name": "New Task Name",       // Required: Title of the work item
  "field_value_pairs": [         // Optional: Custom fields
    {
      "field_key": "priority",
      "field_value": "high"
    }
  ]
}
```

**Response (JSON):**
```json
{
  "data": 123456789, // The ID of the created work item
  "code": 0,
  "msg": "success"
}
```

---

### 2.2 Filter Work Items (Single Project)
Query work items within a specific project using various filters.

- **Method**: `POST`
- **Path**: `/open_api/:project_key/work_item/filter`
- **URL Params**:
  - `project_key`: The unique key of the project.

**Request Body (JSON):**
```json
{
  "page_num": 1,
  "page_size": 20,
  "work_item_name": "keyword",     // Optional: Filter by name
  "work_item_type_keys": ["task"], // Optional: Filter by types
  "work_item_status": [],          // Optional: Filter by status
  "created_at": {                  // Optional: Time range
    "start": 1600000000,
    "end": 1700000000
  }
}
```

**Response (JSON):**
```json
{
  "data": [
    {
      "id": 123,
      "name": "Task Name",
      "project_key": "PROJ",
      "work_item_type_key": "task",
      ...
    }
  ],
  "pagination": {
    "total": 100,
    "page_num": 1,
    "page_size": 20
  }
}
```

---

### 2.3 Filter Work Items (Across Projects)
Query work items across multiple projects.

- **Method**: `POST`
- **Path**: `/open_api/work_items/filter_across_project`

**Request Body (JSON):**
```json
{
  "project_keys": ["PROJ1", "PROJ2"], // Required: List of projects
  "work_item_type_key": "task",       // Optional
  "page_num": 1,
  "page_size": 50
}
```

---

### 2.4 Advanced Search (Search By Params)
Complex search with nested conditions.

- **Method**: `POST`
- **Path**: `/open_api/:project_key/work_item/:work_item_type_key/search/params`
- **URL Params**:
  - `project_key`: Project Key
  - `work_item_type_key`: Work Item Type Key

**Request Body (JSON):**
```json
{
  "search_group": {
    "conjunction": "AND",
    "search_params": [
      {
        "field_key": "created_by",
        "operator": "IN",
        "value": ["user_id_1"]
      }
    ]
  },
  "fields": ["name", "priority", "status"], // Fields to return
  "page_num": 1,
  "page_size": 20
}
```

## 3. Python Implementation Example

Here is how to call the API using Python's `httpx` library (async).

```python
import httpx
import asyncio

BASE_URL = "https://project.feishu.cn"

async def create_work_item(project_key: str, user_token: str, user_key: str, name: str, type_key: str = "task"):
    url = f"{BASE_URL}/open_api/{project_key}/work_item/create"
    
    headers = {
        "X-PLUGIN-TOKEN": user_token,
        "X-USER-KEY": user_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "work_item_type_key": type_key,
        "name": name
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()

# Usage
# asyncio.run(create_work_item("MY_PROJ", "token_xxx", "user_xxx", "Fix Login Bug"))
```
