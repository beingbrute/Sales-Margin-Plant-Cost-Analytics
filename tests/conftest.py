"""Shared test setup: one database connection, every test rolled back afterwards.

The tests read the database after a full load:
    python src/load_data.py --port 5433
Then:
    python -m pytest -s -v tests --port 5433
(-s lets pytest show the password prompt.)
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
KEY = ROOT / "data" / "answer_key"
sys.path.insert(0, str(ROOT / "src"))

from db import connect  # noqa: E402


def pytest_addoption(parser):
    parser.addoption("--host", default="localhost")
    parser.addoption("--port", default="5432")
    parser.addoption("--user", default="postgres")


@pytest.fixture(scope="session")
def con(request):
    args = SimpleNamespace(host=request.config.getoption("--host"),
                           port=request.config.getoption("--port"),
                           user=request.config.getoption("--user"))
    c = connect(args)
    yield c
    c.close()


@pytest.fixture
def cur(con):
    """A cursor inside a transaction that is always rolled back, so tests never change the data."""
    with con.cursor() as c:
        yield c
    con.rollback()


@pytest.fixture
def one(cur):
    def _one(sql, params=()):
        cur.execute(sql, params)
        return cur.fetchone()[0]
    return _one


@pytest.fixture
def query(con):
    """Runs a query and returns a DataFrame; numeric columns come back as floats."""
    def _query(sql, params=()):
        with con.cursor() as c:
            c.execute(sql, params)
            cols = [d[0] for d in c.description]
            df = pd.DataFrame(c.fetchall(), columns=cols)
        con.rollback()
        for col in df.columns:
            if df[col].dtype == object:
                try:
                    df[col] = pd.to_numeric(df[col])
                except (ValueError, TypeError):
                    pass
        return df
    return _query


def raw(path, **kw):
    """Reads a generated source file (data/raw/...) as the independent input."""
    return pd.read_csv(RAW / path, **kw)
