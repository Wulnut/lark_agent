---
name: async-python-patterns
description: Master Python asyncio, concurrent programming, and async/await patterns for high-performance applications. 当构建异步 API、并发系统或需要非阻塞操作的 I/O 密集型应用时使用此 skill。
---

# Async Python Patterns

## 适用场景

- 构建异步 Web API（FastAPI、aiohttp、Sanic）
- 实现并发 I/O 操作（数据库、文件、网络）
- 创建并发请求的网络爬虫
- 开发实时应用（WebSocket 服务器、聊天系统）
- 同时处理多个独立任务
- 构建异步通信的微服务
- 优化 I/O 密集型工作负载
- 实现异步后台任务和队列

## 核心概念

### 1. Event Loop

事件循环是 asyncio 的核心，管理和调度异步任务。

### 2. Coroutines

使用 `async def` 定义的可暂停和恢复的函数。

### 3. Tasks

在事件循环上并发运行的已调度协程。

### 4. Futures

表示异步操作最终结果的底层对象。

## 快速开始

```python
import asyncio

async def main():
    print("Hello")
    await asyncio.sleep(1)
    print("World")

asyncio.run(main())
```

## 基础模式

### 并发执行 gather()

```python
async def fetch_all_users(user_ids: List[int]) -> List[dict]:
    tasks = [fetch_user(uid) for uid in user_ids]
    results = await asyncio.gather(*tasks)
    return results
```

### 超时处理

```python
try:
    result = await asyncio.wait_for(slow_operation(5), timeout=2.0)
except asyncio.TimeoutError:
    print("Operation timed out")
```

### Semaphore 限流

```python
async def api_call(url: str, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        await asyncio.sleep(0.5)
        return {"url": url, "status": 200}

async def rate_limited_requests(urls: List[str], max_concurrent: int = 5):
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [api_call(url, semaphore) for url in urls]
    return await asyncio.gather(*tasks)
```

## 常见陷阱

### 1. 忘记 await

```python
# 错误 - 返回协程对象，不执行
result = async_function()

# 正确
result = await async_function()
```

### 2. 阻塞事件循环

```python
# 错误 - 阻塞
import time
async def bad():
    time.sleep(1)

# 正确 - 非阻塞
async def good():
    await asyncio.sleep(1)
```

### 3. 混合同步和异步代码

```python
# 正确方式
def sync_function():
    result = asyncio.run(async_function())
```

## 最佳实践

1. **使用 asyncio.run()** 作为入口点（Python 3.7+）
2. **始终 await 协程** 以执行它们
3. **使用 gather() 并发执行** 多个任务
4. **实现正确的错误处理** 使用 try/except
5. **使用超时** 防止操作挂起
6. **使用连接池** 提高性能
7. **避免阻塞操作** 在异步代码中
8. **使用 semaphore** 限流
9. **正确处理任务取消**
10. **使用 pytest-asyncio** 测试异步代码
