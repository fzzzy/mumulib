

.PHONY: all build serve clean test mypy lint


all: node_modules build serve
	echo "Done"


build: mumulib-venv dist


mumulib-venv:
	uv venv mumulib-venv
	uv pip install --python mumulib-venv -e "python[dev]"



node_modules:
	npm install


dist: node_modules
	node esbuild.js


serve:
	node esbuild.js --serve


clean:
	rm -rf node_modules && rm -rf mumulib-venv && rm -rf dist && rm -rf python/mumulib/__pycache__


test: mumulib-venv
	@echo "Running tests with coverage..."
	@. mumulib-venv/bin/activate && cd python/mumulib && \
		rm -f .coverage .coverage.* && \
		python consumers_test.py > /dev/null 2>&1 && \
		mv .coverage .coverage.consumers && \
		python shaped_test.py > /dev/null 2>&1 && \
		mv .coverage .coverage.shaped && \
		python mumutypes_test.py > /dev/null 2>&1 && \
		mv .coverage .coverage.mumutypes && \
		python producers_test.py > /dev/null 2>&1 && \
		mv .coverage .coverage.producers && \
		python server_test.py > /dev/null 2>&1 && \
		mv .coverage .coverage.server && \
		coverage combine .coverage.* && \
		echo "" && \
		echo "=== Combined Coverage Report ===" && \
		coverage report -m


mypy: mumulib-venv
	. mumulib-venv/bin/activate && cd python && mypy


lint:
	@echo "Running flake8 linter..."
	@cd python/mumulib && flake8 . --exclude=mumulib-venv,__pycache__,.coverage*,*.pyc --max-line-length=120 --statistics


tags:
	. mumulib-venv/bin/activate && python3 python/mumulib/tags.py

