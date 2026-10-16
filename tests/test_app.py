"""Smoke test for the Streamlit page: run the script headless and check it renders a table."""

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")


def test_streamlit_page_renders_without_exception():
    at = st_testing.AppTest.from_file("../app.py", default_timeout=30).run()
    assert not at.exception
    assert len(at.dataframe) == 1
    assert at.dataframe[0].value.shape == (6, 11)  # SF7..SF12 rows, 11 columns
    assert at.title[0].value.startswith("LoRa")
