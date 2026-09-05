

.PHONY: all build serve clean test mypy lint python-sync mumulib-venv tags


all: node_modules build serve
	echo "Done"


build: mumulib-venv dist


# Keep the old target as an alias for callers; uv owns python/.venv.
mumulib-venv: python-sync

python-sync:
	uv sync --project python --extra dev --locked


node_modules: package.json package-lock.json
	npm ci
	touch node_modules


dist: node_modules
	node esbuild.js


serve:
	node esbuild.js --serve


clean:
	rm -rf node_modules && rm -rf mumulib-venv python/.venv && rm -rf dist && rm -rf python/mumulib/__pycache__


test: mumulib-venv
	@echo "Running tests with coverage..."
	@cd python/mumulib && \
		rm -f .coverage .coverage.* && \
		uv run --project .. --extra dev --locked python consumers_test.py && \
		mv .coverage .coverage.consumers && \
		uv run --project .. --extra dev --locked python shaped_test.py && \
		mv .coverage .coverage.shaped && \
		uv run --project .. --extra dev --locked python mumutypes_test.py && \
		mv .coverage .coverage.mumutypes && \
		uv run --project .. --extra dev --locked python producers_test.py && \
		mv .coverage .coverage.producers && \
		uv run --project .. --extra dev --locked python server_test.py && \
		mv .coverage .coverage.server && \
		uv run --project .. --extra dev --locked coverage combine .coverage.* && \
		echo "" && \
		echo "=== Combined Coverage Report ===" && \
		uv run --project .. --extra dev --locked coverage report -m


mypy: mumulib-venv
	cd python && uv run --extra dev --locked mypy


lint: python-sync
	@echo "Running flake8 linter..."
	@cd python/mumulib && uv run --project .. --extra dev --locked flake8 . --exclude=mumulib-venv,__pycache__,.coverage*,*.pyc --max-line-length=120 --ignore=E402 --statistics


tags: python-sync
	uv run --project python --extra dev --locked python python/mumulib/tags.py

