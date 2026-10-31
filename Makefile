.PHONY: fonts lint test

lint:
	uv lock --check

test:
	@set -e; for config in airgradient-*.yaml; do \
		uv run --frozen esphome config "$$config" >/dev/null; \
	done

fonts:
	uv run --frozen python scripts/prepare_display_font.py
