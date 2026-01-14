import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.providers.project.work_item_provider import WorkItemProvider

@pytest.fixture
def mock_work_item_api():
    with patch("src.providers.project.work_item_provider.WorkItemAPI") as mock_cls:
        yield mock_cls.return_value

@pytest.fixture
def mock_metadata():
    with patch("src.providers.project.work_item_provider.MetadataManager") as mock_cls:
        mock_instance = AsyncMock()
        mock_cls.get_instance.return_value = mock_instance
        yield mock_instance

@pytest.mark.asyncio
async def test_get_tasks_related_to_concurrency(mock_work_item_api, mock_metadata):
    """Test concurrent fetching for related_to logic"""
    # Setup
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.return_value = "type_issue"
    
    # Simulate 8 pages of data (400 items total, 50 per page)
    # Target related_to ID is 999. It appears in page 1 and page 6.
    
    async def mock_filter(project_key, work_item_type_keys, page_num, page_size, **kwargs):
        # Verify page size matches BATCH_SIZE (50)
        assert page_size == 50
        
        items = []
        # Generate 50 items for this page
        for i in range(50):
            item_id = (page_num - 1) * 50 + i
            item = {
                "id": item_id,
                "name": f"Task {item_id}",
                "fields": []
            }
            
            # Add related_to field for specific items
            if item_id == 10: # Page 1
                item["fields"].append({"field_value": 999})
            elif item_id == 260: # Page 6 (starts at 250)
                item["fields"].append({"field_value": [999, 888]})
                
            items.append(item)
            
        # Stop after page 8
        if page_num > 8:
            return {"work_items": [], "total": 400}
            
        return {"work_items": items, "total": 400}

    mock_work_item_api.filter.side_effect = mock_filter

    provider = WorkItemProvider("My Project")
    
    # Execute
    result = await provider.get_tasks(related_to=999)
    
    # Verify
    items = result["items"]
    assert len(items) == 2
    ids = sorted([item["id"] for item in items])
    assert ids == [10, 260]
    
    # Check if filter was called multiple times
    # We expect pages 1-5 (batch 1) and 6-8 (batch 2) to be fetched.
    # Total pages fetched should be at least 6 (since we found items in page 6)
    # Actually, the loop continues until total_fetched >= 2000 or MAX_PAGES reached or empty page.
    # Our mock returns items up to page 8. 
    # Logic: 
    # Batch 1: Pages 1-5. total_fetched becomes 250.
    # Batch 2: Pages 6-10.
    #   Page 6, 7, 8 return 50 items.
    #   Page 9, 10 return empty (mock logic > 8 returns empty).
    # loop checks `if len(items) < BATCH_SIZE`. Empty page triggers this.
    # So it should stop after Batch 2.
    
    assert mock_work_item_api.filter.call_count >= 8
