from contextlib import contextmanager

import pytest
import requests
import tableauserverclient as TSC

from app.core.errors import PublishError
from app.tableau.publisher import publish_or_overwrite


class FakeDatasources:
    def __init__(self, behavior):
        self.behavior = behavior  # list of things to do/raise per call, or a plain return value
        self.calls = 0

    def publish(self, datasource_item, file_path, mode):
        self.calls += 1
        step = self.behavior
        if isinstance(step, list):
            step = step[min(self.calls - 1, len(step) - 1)]
        if isinstance(step, Exception):
            raise step
        return step


class FakeServer:
    def __init__(self, datasources):
        self.datasources = datasources


class FakeClient:
    def __init__(self, server):
        self._server = server

    @contextmanager
    def session(self):
        yield self._server


class FakePublishedDatasource:
    def __init__(self, luid):
        self.id = luid


def test_publish_or_overwrite_returns_luid_on_success():
    fake_ds = FakeDatasources(behavior=FakePublishedDatasource("luid-123"))
    client = FakeClient(FakeServer(fake_ds))

    luid = publish_or_overwrite(client, "project-1", "orders-revenue", "/tmp/fake.hyper")

    assert luid == "luid-123"
    assert fake_ds.calls == 1


def test_publish_uses_overwrite_mode_so_reruns_dont_duplicate():
    captured = {}

    class CapturingDatasources(FakeDatasources):
        def publish(self, datasource_item, file_path, mode):
            captured["mode"] = mode
            return FakePublishedDatasource("luid-1")

    client = FakeClient(FakeServer(CapturingDatasources(behavior=None)))
    publish_or_overwrite(client, "project-1", "orders-revenue", "/tmp/fake.hyper")

    assert captured["mode"] == TSC.Server.PublishMode.Overwrite


def test_publish_wraps_server_rejection_as_non_retryable_publish_error():
    fake_error = TSC.ServerResponseError("code", "Permission denied", "detail")
    fake_ds = FakeDatasources(behavior=fake_error)
    client = FakeClient(FakeServer(fake_ds))

    with pytest.raises(PublishError) as exc_info:
        publish_or_overwrite(client, "project-1", "orders-revenue", "/tmp/fake.hyper")

    assert exc_info.value.retryable is False
    assert fake_ds.calls == 1  # no retry on an explicit rejection


def test_publish_retries_network_errors_then_succeeds():
    fake_ds = FakeDatasources(
        behavior=[
            requests.exceptions.ConnectionError("network blip 1"),
            requests.exceptions.ConnectionError("network blip 2"),
            FakePublishedDatasource("luid-after-retry"),
        ]
    )
    client = FakeClient(FakeServer(fake_ds))

    luid = publish_or_overwrite(client, "project-1", "orders-revenue", "/tmp/fake.hyper")

    assert luid == "luid-after-retry"
    assert fake_ds.calls == 3


def test_publish_gives_up_after_max_retries_on_persistent_network_failure():
    fake_ds = FakeDatasources(behavior=[requests.exceptions.ConnectionError("down")] * 5)
    client = FakeClient(FakeServer(fake_ds))

    with pytest.raises(PublishError) as exc_info:
        publish_or_overwrite(client, "project-1", "orders-revenue", "/tmp/fake.hyper")

    assert exc_info.value.retryable is True
    assert fake_ds.calls == 3  # stop_after_attempt(3)
