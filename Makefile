.PHONY: check lint fix typecheck test py-test browser-test build dist python-sync \
	run stop tail dev clean tags

# The examples' dev server, and where its output goes
PORT := 8000
LOG := $(CURDIR)/var/log

# Every tool through uv, from python/, so each reads python/pyproject.toml and
# leaves its caches and .coverage there rather than at the root.
UV := uv run --directory python --extra dev --locked


check: lint typecheck build test


lint: python-sync
	$(UV) ruff check
	$(UV) ruff format --check

fix: python-sync
	$(UV) ruff check --fix
	$(UV) ruff format

typecheck: node_modules python-sync
	npm run test:unit
	$(UV) pyright


test: py-test browser-test

py-test: python-sync
	$(UV) pytest --cov=mumulib --cov-branch

# Against Vite's dev server, instrumented; nyc then reports what src/ ran
browser-test: node_modules
	npm run test:browser
	npm run coverage


build: python-sync dist

dist: node_modules
	npm run build

python-sync:
	uv sync --project python --extra dev --locked

node_modules: package.json package-lock.json
	npm ci
	touch node_modules


# The examples, served from source at http://127.0.0.1:$(PORT)/
run: node_modules
	@mkdir -p "$(LOG)"
	@$(MAKE) --no-print-directory stop > /dev/null
	@exec npx vite > "$(LOG)/vite.log" 2>&1 < /dev/null &
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		lsof -ti tcp:$(PORT) -sTCP:LISTEN > /dev/null && break; sleep 0.5; \
	done; \
	if lsof -ti tcp:$(PORT) -sTCP:LISTEN > /dev/null; then \
		echo "Examples: http://127.0.0.1:$(PORT)/"; \
		echo "Logs:     make tail"; \
		echo "Stop:     make stop"; \
	else \
		echo "Vite did not start; see $(LOG)/vite.log" >&2; exit 1; \
	fi

# Whatever holds the port is the server, whatever started it
stop:
	@pids=$$(lsof -ti tcp:$(PORT) -sTCP:LISTEN); \
	if [ -z "$$pids" ]; then echo "Not running."; exit 0; fi; \
	kill $$pids; \
	for i in 1 2 3 4 5 6 7 8 9 10; do \
		lsof -ti tcp:$(PORT) -sTCP:LISTEN > /dev/null || { echo "Stopped."; exit 0; }; \
		sleep 0.3; \
	done; \
	echo "Still holding port $(PORT) after SIGTERM; sending SIGKILL."; \
	kill -9 $$(lsof -ti tcp:$(PORT) -sTCP:LISTEN) 2> /dev/null; \
	sleep 0.5; \
	if lsof -ti tcp:$(PORT) -sTCP:LISTEN > /dev/null; then \
		echo "Port $(PORT) is still held." >&2; exit 1; \
	fi; \
	echo "Stopped."

tail:
	@tail -f "$(LOG)/vite.log"

dev: run tail


clean:
	rm -rf node_modules python/.venv dist var .nyc_output coverage-frontend
	find python -name __pycache__ -prune -exec rm -rf {} +


tags: python-sync
	$(UV) python mumulib/tags.py
