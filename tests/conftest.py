import logging
import pytest
import asyncio
import sys


# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)
logger.info("Test logging configured: level=DEBUG")


# Enable asyncio support for pytest
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    logger.debug("Creating event loop for test session")
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    logger.debug("Closing event loop")
    loop.close()


@pytest.fixture(autouse=True)
def log_test_start(request):
    """Log test start and end for each test."""
    logger.info("=" * 80)
    logger.info("Starting test: %s", request.node.name)
    yield
    logger.info("Completed test: %s", request.node.name)
    logger.info("=" * 80)
