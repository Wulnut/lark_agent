import pytest
import respx
from httpx import Response
from src.core.auth import AuthManager
from src.core.config import settings


@pytest.mark.asyncio
async def test_auth_manager_static_token(monkeypatch):
    """测试使用 settings 中的静态 token"""
    monkeypatch.setattr(settings, "FEISHU_PROJECT_USER_TOKEN", "static_token")
    manager = AuthManager()
    token = await manager.get_plugin_token()
    assert token == "static_token"


@pytest.mark.asyncio
async def test_auth_manager_fetch_token(respx_mock, monkeypatch):
    """测试从 API 获取 token"""
    monkeypatch.setattr(settings, "FEISHU_PROJECT_USER_TOKEN", None)
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_ID", "pid")
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_SECRET", "psec")

    mock_resp = {"code": 0, "data": {"plugin_token": "fetched_token", "expire": 7200}}
    respx_mock.post("https://project.feishu.cn/open_api/authen/plugin_token").mock(
        return_value=Response(200, json=mock_resp)
    )

    manager = AuthManager()
    token = await manager.get_plugin_token()
    assert token == "fetched_token"
    assert manager._plugin_token == "fetched_token"


@pytest.mark.asyncio
async def test_auth_manager_caching(respx_mock, monkeypatch):
    """测试 token 缓存机制"""
    monkeypatch.setattr(settings, "FEISHU_PROJECT_USER_TOKEN", None)
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_ID", "pid")
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_SECRET", "psec")

    route = respx_mock.post(
        "https://project.feishu.cn/open_api/authen/plugin_token"
    ).mock(
        return_value=Response(
            200, json={"code": 0, "data": {"plugin_token": "t1", "expire": 3600}}
        )
    )

    manager = AuthManager()
    await manager.get_plugin_token()
    await manager.get_plugin_token()

    # 应该只调用一次 API
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_auth_manager_no_credentials(monkeypatch):
    """测试未配置凭证时的行为"""
    monkeypatch.setattr(settings, "FEISHU_PROJECT_USER_TOKEN", None)
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_ID", None)
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_SECRET", None)

    manager = AuthManager()
    token = await manager.get_plugin_token()

    # 无凭证时应返回 None
    assert token is None


@pytest.mark.asyncio
async def test_auth_manager_token_expiration_refresh(respx_mock, monkeypatch):
    """测试 token 过期后刷新"""
    monkeypatch.setattr(settings, "FEISHU_PROJECT_USER_TOKEN", None)
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_ID", "pid")
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_SECRET", "psec")

    from dataclasses import dataclass

    @dataclass
    class Counter:
        value: int = 0

    counter = Counter()

    def mock_token_response(request):
        counter.value += 1
        token = f"token_{counter.value}"
        return Response(
            200, json={"code": 0, "data": {"plugin_token": token, "expire": 1}}
        )

    route = respx_mock.post(
        "https://project.feishu.cn/open_api/authen/plugin_token"
    ).mock(side_effect=mock_token_response)

    manager = AuthManager()

    # 第一次调用 - 获取 token
    token1 = await manager.get_plugin_token()
    assert token1 == "token_1"
    assert counter.value == 1

    # 等待 token 过期 (expire=1 秒, buffer=60s, 所以强制设置过期)
    manager._expiry_time = 0

    # 第二次调用 - 应该刷新 token
    token2 = await manager.get_plugin_token()
    assert token2 == "token_2"
    assert counter.value == 2


@pytest.mark.asyncio
async def test_auth_manager_non_standard_api_response(respx_mock, monkeypatch):
    """测试非标准 API 响应格式的处理"""
    monkeypatch.setattr(settings, "FEISHU_PROJECT_USER_TOKEN", None)
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_ID", "pid")
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_SECRET", "psec")

    # 情况 1: 响应中没有 'code' 字段
    respx_mock.post("https://project.feishu.cn/open_api/authen/plugin_token").mock(
        return_value=Response(
            200, json={"plugin_token": "direct_token", "expire": 7200}
        )
    )

    manager = AuthManager()
    token = await manager.get_plugin_token()
    assert token == "direct_token"


@pytest.mark.asyncio
async def test_auth_manager_api_error_response(respx_mock, monkeypatch):
    """测试 API 错误响应的处理"""
    monkeypatch.setattr(settings, "FEISHU_PROJECT_USER_TOKEN", None)
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_ID", "pid")
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_SECRET", "psec")

    # API 返回错误码
    respx_mock.post("https://project.feishu.cn/open_api/authen/plugin_token").mock(
        return_value=Response(200, json={"code": -1, "msg": "Invalid credentials"})
    )

    manager = AuthManager()
    token = await manager.get_plugin_token()

    # API 错误时应返回 None
    assert token is None


@pytest.mark.asyncio
async def test_auth_manager_missing_token_in_response(respx_mock, monkeypatch):
    """测试响应中缺少 token 字段的处理"""
    monkeypatch.setattr(settings, "FEISHU_PROJECT_USER_TOKEN", None)
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_ID", "pid")
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_SECRET", "psec")

    # 响应缺少 plugin_token 字段
    respx_mock.post("https://project.feishu.cn/open_api/authen/plugin_token").mock(
        return_value=Response(200, json={"code": 0, "data": {"expire": 7200}})
    )

    manager = AuthManager()
    token = await manager.get_plugin_token()

    # 缺少 token 时应返回 None
    assert token is None


@pytest.mark.asyncio
async def test_auth_manager_http_error(respx_mock, monkeypatch):
    """测试 HTTP 错误的处理"""
    monkeypatch.setattr(settings, "FEISHU_PROJECT_USER_TOKEN", None)
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_ID", "pid")
    monkeypatch.setattr(settings, "FEISHU_PROJECT_PLUGIN_SECRET", "psec")

    # API 返回 500 错误
    respx_mock.post("https://project.feishu.cn/open_api/authen/plugin_token").mock(
        return_value=Response(500, json={"error": "Internal Server Error"})
    )

    manager = AuthManager()
    token = await manager.get_plugin_token()

    # HTTP 错误时应返回 None
    assert token is None
