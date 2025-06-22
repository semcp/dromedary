.PHONY: test

test:
	./scripts/run_tests.sh

run:
	uv run -m dromedary.agent @mcp_servers/mcp-servers-config.json --policy-config policies/policies.yaml