# Auto-detect Python command (python3 or python)
PYTHON := $(shell command -v python3 || command -v python)
# Use venv Python if available, otherwise system Python
VENV_PYTHON := $(shell [ -f .venv/bin/python ] && echo .venv/bin/python || echo $(PYTHON))

.PHONY: install check test lint format run notebook clean help

help:            ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

check:           ## Verify the environment is ready (run before the lesson)
	$(VENV_PYTHON) check_env.py

install:         ## Create virtual environment and install all dependencies
	$(PYTHON) -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"
	@echo ""
	@echo "✓ Done. Activate with: source .venv/bin/activate"
	make check

test:            ## Run the test suite
	pytest tests/ -v

lint:            ## Check code style with ruff
	ruff check .
	ruff format --check .

format:          ## Auto-format code with ruff
	ruff format .
	ruff check --fix .

run:             ## Launch the Streamlit dashboard
	streamlit run app.py

notebook:        ## Launch Jupyter Lab for exercises
	jupyter lab exercises/

clean:           ## Remove build artefacts and caches
	rm -rf .venv __pycache__ .pytest_cache dist build *.egg-info
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +
