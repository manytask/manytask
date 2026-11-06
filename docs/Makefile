# Diplodoc: from repo root: `make -C docs`; from docs/: `make` or `make docs`.
# Keep generated pages outside the input tree to avoid reprocessing stale output.
DOCS_HTML_DIR := ../build/docs

.PHONY: docs install-deps

docs:
	@command -v npm >/dev/null 2>&1 || { echo "\033[0;31mError: npm is not installed.\033[0m"; exit 1; }
	@test -x node_modules/.bin/yfm || { echo "Error: docs dependencies are missing. Run: make install-deps"; exit 1; }
	npm run build -- --output $(DOCS_HTML_DIR)

install-deps:
	npm ci
