.PHONY: test

check-uv:
	@if ! command -v uv &> /dev/null; then \
		echo "uv is not installed. Installing uv with curl..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi

test: check-uv
	./scripts/run_tests.sh

run: check-uv
	uv run -m dromedary.agent @mcp_servers/mcp-servers-config.json --policy-config policies/policies.yaml