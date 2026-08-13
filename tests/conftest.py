"""Keep the test suite out of the working copy.

Importing ``app`` builds a real application, and a real application opens a
real database at ``config.DATA_DIR``. Left alone that is ``./data`` in the
checkout, so simply collecting the tests would create ``data/radiorumble.db``
next to the source -- and on a machine where somebody had actually used the
app, run the suite against their fixture list and their admin password.

This is not a hypothetical. The sister project in this repo group lost three
CI runs to precisely that shape: one test in nine hundred built the app with
its default configuration, wrote a schema into the working tree, and hung the
build for an hour on a slow disk while every other test ran from a tmpfs.

So the environment is pointed somewhere disposable before anything imports
``radiorumble.config`` -- which has to happen at import time here, because that
module reads ``RR_DATA_DIR`` once, into a module-level constant. A fixture
would be far too late: by the time one ran, the constant would already be set.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="rr-tests-"))
os.environ["RR_DATA_DIR"] = str(_TMP)

import pytest  # noqa: E402  -- after the environment is set, deliberately


@pytest.fixture
def data_dir() -> Path:
    """Where this run's database lives, for a test that wants to look."""
    return _TMP
