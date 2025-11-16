import asyncio
import time

import pytest


@pytest.fixture
def sleep_calls(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Fixture that spies on time.sleep and records delays

    It patches `time.sleep` with a spy that still calls the real
    sleep so behaviour is unchanged, but it records the requested delays
    in a list which the test can inspect.

    Args:
        monkeypatch: pytest monkeypatch fixture

    Returns:
        recorded delays passed to time.sleep
    """
    real_sleep = time.sleep
    call_list = []

    def spy_sleep(delay):
        call_list.append(delay)
        real_sleep(delay)

    monkeypatch.setattr(time, "sleep", spy_sleep)

    return call_list


@pytest.fixture
def asyncio_sleep_calls(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Fixture that spies on asyncio.sleep and records delays

    It patches `asyncio.sleep` with a spy that still awaits the real
    sleep so behaviour is unchanged, but it records the requested delays
    in a list which the test can inspect.

    Args:
        monkeypatch: pytest monkeypatch fixture

    Returns:
        recorded delays passed to asyncio.sleep
    """
    real_sleep = asyncio.sleep
    call_list = []

    async def spy_asyncio_sleep(delay, *args, **kwargs):
        call_list.append(delay)
        await real_sleep(delay, *args, **kwargs)

    monkeypatch.setattr(asyncio, "sleep", spy_asyncio_sleep)

    return call_list
