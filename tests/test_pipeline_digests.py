# test_pipeline_digests.py
"""Digest sending in run_pipeline does not depend on papers being fetched."""

from argparse import Namespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from preprint_bot import pipeline


def _args(date=None):
    return Namespace(
        date=date,
        model="m",
        skip_download=True,
        skip_parse=True,
        skip_embed=True,
        skip_summarize=True,
        summarizer="transformer",
        llm_model="",
    )


@pytest.mark.asyncio
async def test_digests_sent_when_no_papers_fetched(tmp_path):
    api_client = MagicMock()
    api_client.create_processing_run = AsyncMock(return_value={"id": 1})
    api_client.update_processing_run = AsyncMock()
    api_client.close = AsyncMock()
    send = AsyncMock()

    with (
        patch.object(pipeline, "_preflight_checks"),
        patch.object(pipeline, "APIClient", return_value=api_client),
        patch.object(
            pipeline,
            "process_unprocessed_papers",
            AsyncMock(return_value={"parsed": 0, "embedded": 0}),
        ),
        patch.object(
            pipeline,
            "get_all_profile_categories",
            AsyncMock(return_value={"arxiv": ["cs.AI"]}),
        ),
        patch.object(pipeline, "fetch_preprint_papers", AsyncMock(return_value=[])),
        patch.object(pipeline, "store_fetched_papers") as store,
        patch.object(pipeline, "send_all_digests", send),
        patch.object(pipeline, "PDF_DIR", tmp_path),
    ):
        # A Saturday that is also the 1st of the month
        await pipeline.run_pipeline(_args(date="2026-08-01"))

    store.assert_not_called()
    send.assert_awaited_once_with(api_client, run_date="2026-08-01")
