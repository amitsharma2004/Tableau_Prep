"""Publishes a .hyper file as a Tableau datasource. Idempotent by design:
TSC's PublishMode.Overwrite replaces any existing datasource of the same
name in the target project rather than creating a duplicate (build plan
'idempotent publish') - callers should always pass the same
`datasource_name` for a given flow (see Flow.target_datasource_name).

Retry policy: only network-level failures (couldn't reach the server) are
retried - an explicit rejection FROM Tableau (bad project id, permission
denied, invalid file) won't succeed on retry, so those fail fast with a
clear message instead (build plan 'Tableau publish failures').
"""
from __future__ import annotations

from pathlib import Path

import requests
import tableauserverclient as TSC
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.errors import PublishError
from app.tableau.client import TableauClient

_NETWORK_EXCEPTIONS = (requests.exceptions.ConnectionError, requests.exceptions.Timeout)


@retry(
    retry=retry_if_exception_type(_NETWORK_EXCEPTIONS),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _publish_with_retry(server, datasource_item: TSC.DatasourceItem, file_path: str):
    return server.datasources.publish(datasource_item, file_path, TSC.Server.PublishMode.Overwrite)


def publish_or_overwrite(
    client: TableauClient,
    project_id: str,
    datasource_name: str,
    hyper_file_path: str | Path,
) -> str:
    """Returns the published datasource's LUID."""
    datasource_item = TSC.DatasourceItem(project_id, name=datasource_name)

    try:
        with client.session() as server:
            published = _publish_with_retry(server, datasource_item, str(hyper_file_path))
    except TSC.ServerResponseError as exc:
        raise PublishError(f"Tableau rejected the publish: {exc}", retryable=False) from exc
    except _NETWORK_EXCEPTIONS as exc:
        raise PublishError(f"Could not reach Tableau Server after retries: {exc}", retryable=True) from exc

    return published.id
