

.PHONY: all build serve clean


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


tags:
	. mumulib-venv/bin/activate && python3 python/mumulib/tags.py

