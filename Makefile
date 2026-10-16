PY ?= python3
export PYTHONPATH := src

.PHONY: check lint test smoke example app clean

check: lint test

lint:
	ruff check src tests app.py
	ruff format --check src tests app.py

# 40 unit tests (airtime vs published figures, path-loss inverses, duty cycle, battery) + the
# Streamlit page rendered headless with streamlit.testing.
test:
	$(PY) -m pytest -q

# The farm worked example from the README, end to end.
smoke: example

example:
	$(PY) -m lora_link_budget example

# Interactive page on http://localhost:8501
app:
	$(PY) -m streamlit run app.py

clean:
	rm -rf .pytest_cache .ruff_cache
