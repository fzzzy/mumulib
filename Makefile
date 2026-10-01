.PHONY: check lint fix typecheck test py-test browser-test node-test build dist \
	python-sync \
	node_modules run stop tail dev server server-exists clean tags

# The examples' dev server, and where its output goes
PORT := 8000
LOG := $(CURDIR)/var/log

# make run and make server run one of py/examples: SERVER=<name> for another
# than hello
SERVER ?= hello
SERVER_PORT ?= 8001
# Reloading as the code changes; and on stop, waiting at most two seconds
# for open responses. Event streams end themselves on a signal; this is for
# anything else that would keep a stop waiting.
UVICORN_FLAGS := --reload --timeout-graceful-shutdown 2

# The TypeScript library is in ts/ and the Python one in py/. Every Python tool
# runs through uv from py/, so each reads py/pyproject.toml and leaves its
# caches and .coverage there; every npm script runs in ts/.
UV := uv run --directory py --extra dev --locked
NPM := cd ts && npm


check: lint typecheck build test


lint: node_modules python-sync
	$(NPM) run lint
	$(UV) ruff check
	$(UV) ruff format --check

fix: node_modules python-sync
	$(NPM) run format
	$(UV) ruff check --fix
	$(UV) ruff format

typecheck: node_modules python-sync
	$(NPM) run test:unit
	cd ts && node src/vite/sfc-check.mjs --project tsconfig.examples.json examples
	$(UV) pyright


test: py-test browser-test node-test

py-test: python-sync
	$(UV) pytest --cov=mumulib --cov-branch

# Against Vite's dev server, instrumented; nyc then reports what ts/src/ ran
browser-test: node_modules
	$(NPM) run test:browser
	$(NPM) run coverage

# The package as published, installed and used from Node, with domino's DOM
node-test: dist
	cd ts && node scripts/node-check.mjs


build: python-sync dist

dist: node_modules
	$(NPM) run build

python-sync:
	uv sync --project py --extra dev --locked

node_modules: ts/node_modules

ts/node_modules: ts/package.json ts/package-lock.json
	$(NPM) ci
	touch ts/node_modules


# The examples in the background: the TypeScript ones from Vite at
# http://127.0.0.1:$(PORT)/, and a Python one (SERVER=<name>) from uvicorn at
# http://127.0.0.1:$(SERVER_PORT)/, each reloading as its code changes and
# logging to var/log. A service is whatever holds its port: run frees both
# ports first, stop signals whatever holds them, and neither needs a pidfile.
run: node_modules python-sync server-exists
	@mkdir -p "$(LOG)"
	@$(MAKE) --no-print-directory stop > /dev/null
	@cd ts && exec npx vite > "$(LOG)/vite.log" 2>&1 < /dev/null &
	@PYTHONUNBUFFERED=1 exec $(UV) uvicorn examples.$(SERVER):app \
		--host 127.0.0.1 --port $(SERVER_PORT) $(UVICORN_FLAGS) \
		> "$(LOG)/server.log" 2>&1 < /dev/null &
	@$(call wait_for_port,$(PORT),vite)
	@$(call wait_for_port,$(SERVER_PORT),server)
	@echo "Examples: http://127.0.0.1:$(PORT)/"
	@echo "Python:   http://127.0.0.1:$(SERVER_PORT)/  (examples/$(SERVER).py)"
	@echo "Logs:     make tail"
	@echo "Stop:     make stop"

stop:
	@$(call stop_port,$(PORT),Vite)
	@$(call stop_port,$(SERVER_PORT),The Python server)

# -F rather than -f: a log run truncates is followed from its new start
tail:
	@tail -F "$(LOG)/vite.log" "$(LOG)/server.log"

dev: run tail

# Waits up to ten seconds for $(1) to be listened on, else shows the end of
# var/log/$(2).log and fails
define wait_for_port
for i in $$(seq 20); do \
	lsof -ti tcp:$(1) -sTCP:LISTEN > /dev/null && exit 0; sleep 0.5; \
done; \
echo "Nothing is listening on port $(1); the end of $(LOG)/$(2).log:" >&2; \
tail -20 "$(LOG)/$(2).log" >&2; exit 1
endef

# The processes holding port $(1): listening on it, or bound to it and not
# listening -- as uvicorn's reloader is while the app it runs fails to
# import, which a LISTEN-only search misses though nothing else can bind the
# port. A connection, to or from the port, is someone else's: a browser's.
port_holders = lsof -nP -iTCP:$(1) -sTCP:LISTEN,CLOSED -Fpn \
	| awk '/^p/ { pid = substr($$0, 2) } /^n/ && !/->/ { print pid }' | sort -u

# Succeeds if any of the processes $(1) is still running -- in a subshell,
# so its exit is its own. kill -0 with them all fails as soon as one has
# gone, which would say too early that all have.
any_alive = ( for pid in $(1); do kill -0 $$pid 2> /dev/null && exit 0; done; exit 1 )

# SIGTERM to every process holding $(1) -- uvicorn's reloader and its worker
# both do -- then waits for those processes to be gone, not only the port: a
# server waiting on open connections has closed its listening socket and is
# still running. If any is left after five seconds, SIGKILL, saying so.
define stop_port
pids=$$($(call port_holders,$(1))); \
if [ -z "$$pids" ]; then echo "$(2) was not running (port $(1))."; exit 0; fi; \
kill $$pids 2> /dev/null; \
for i in $$(seq 50); do \
	$(call any_alive,$$pids) || { echo "$(2) stopped (port $(1))."; exit 0; }; \
	sleep 0.1; \
done; \
echo "$(2) was still running five seconds after SIGTERM; sending SIGKILL." >&2; \
kill -9 $$pids 2> /dev/null; \
sleep 0.5; \
if $(call any_alive,$$pids) || [ -n "$$($(call port_holders,$(1)))" ]; then \
	echo "Port $(1) is still held." >&2; exit 1; \
fi; \
echo "$(2) stopped (port $(1))."
endef


# A Python example, in the foreground, reloading as its code changes
server: python-sync server-exists
	$(UV) uvicorn examples.$(SERVER):app --host 127.0.0.1 --port $(SERVER_PORT) \
		$(UVICORN_FLAGS)

server-exists:
	@test -f py/examples/$(SERVER).py || { \
		echo "No py/examples/$(SERVER).py; there are:" \
			$$(cd py/examples && ls *.py | grep -v -e _test -e __init__ | sed 's/\.py$$//') >&2; \
		exit 1; }


clean:
	rm -rf var ts/node_modules ts/dist ts/.nyc_output ts/coverage-frontend py/.venv
	find py -name __pycache__ -prune -exec rm -rf {} +


tags: python-sync
	$(UV) python mumulib/tags.py
