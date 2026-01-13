"""
Integration Test Configuration
集成测试配置 - Track 2: Live Integration Testing

测试环境:
- 项目: 从环境变量 FEISHU_TEST_PROJECT_KEY 或 FEISHU_PROJECT_KEY 读取
- 工作项类型: 问题管理

必须配置的环境变量:
- FEISHU_TEST_PROJECT_KEY 或 FEISHU_PROJECT_KEY
- FEISHU_PROJECT_PLUGIN_ID + FEISHU_PROJECT_PLUGIN_SECRET + FEISHU_PROJECT_USER_KEY
  或 FEISHU_PROJECT_USER_TOKEN + FEISHU_PROJECT_USER_KEY
"""
import pytest
from src.core.config import settings


# =============================================================================
# Integration Test Constants
# =============================================================================
# 优先使用测试专用的 FEISHU_TEST_PROJECT_KEY，否则回退到 FEISHU_PROJECT_KEY
TEST_PROJECT_KEY = settings.FEISHU_TEST_PROJECT_KEY or settings.FEISHU_PROJECT_KEY
TEST_WORK_ITEM_TYPE = "问题管理"


# =============================================================================
# Skip Condition: Check if credentials are available
# =============================================================================
def _has_credentials() -> bool:
    """Check if Feishu credentials are configured (supports both auth methods)."""
    # Must have project key
    if not TEST_PROJECT_KEY:
        return False
    
    # Method 1: User Token + User Key
    has_user_auth = bool(
        settings.FEISHU_PROJECT_USER_TOKEN
        and settings.FEISHU_PROJECT_USER_KEY
    )
    # Method 2: Plugin ID + Plugin Secret
    has_plugin_auth = bool(
        settings.FEISHU_PROJECT_PLUGIN_ID
        and settings.FEISHU_PROJECT_PLUGIN_SECRET
        and settings.FEISHU_PROJECT_USER_KEY  # User Key is still needed
    )
    return has_user_auth or has_plugin_auth


skip_without_credentials = pytest.mark.skipif(
    not _has_credentials(),
    reason="Feishu credentials not configured (need PROJECT_KEY + auth credentials)"
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances after each test to avoid event loop issues."""
    yield
    # Reset ProjectClient singleton after each test
    import src.core.project_client as pc_module
    if pc_module._project_client is not None:
        # Try to close the client gracefully
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                loop.run_until_complete(pc_module._project_client.close())
        except Exception:
            pass
        pc_module._project_client = None


@pytest.fixture
def test_project_key():
    """Return the test project key (from env)."""
    return TEST_PROJECT_KEY


@pytest.fixture
def test_work_item_type():
    """Return the test work item type."""
    return TEST_WORK_ITEM_TYPE
