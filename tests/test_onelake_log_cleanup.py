import os
import time
from pathlib import Path

import pytest

from src.storage.onelake_remote import _upsert

pa = pytest.importorskip("pyarrow")
deltalake = pytest.importorskip("deltalake")


def test_upsert_leaves_expired_delta_log_entries_in_place(tmp_path: Path) -> None:
    uri = str(tmp_path / "usage_daily")
    for key in range(3):
        _upsert(uri, pa.table({"k": [key], "v": [key]}), "s.k = t.k", {}, update_matched=True)
    deltalake.DeltaTable(uri).create_checkpoint()
    log = tmp_path / "usage_daily" / "_delta_log"
    expired = time.time() - 60 * 86400
    for entry in log.iterdir():
        os.utime(entry, (expired, expired))
    before = {entry.name for entry in log.iterdir()}

    _upsert(uri, pa.table({"k": [9], "v": [9]}), "s.k = t.k", {}, update_matched=True)

    assert before <= {entry.name for entry in log.iterdir()}
    assert deltalake.DeltaTable(uri).to_pyarrow_table().num_rows == 4
