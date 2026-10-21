.PHONY: lint test

lint:
	uv lock --check

test:
	@set -e; for config in airgradient-*.yaml; do \
		uv run --frozen esphome config "$$config" >/dev/null; \
	done
