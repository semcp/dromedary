.PHONY: test

check-uv:
	@if ! command -v uv &> /dev/null; then \
		echo "uv is not installed. Installing uv with curl..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi

test: check-uv
	uv run run_tests.py

run: check-uv
	uv run p_llm_agent.py