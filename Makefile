

.PHONY: all build serve clean


all: node_modules build serve
	echo "Done"


build: mumulib node_modules dist


mumulib:
	python3 -m venv mumulib
	. mumulib/bin/activate
	pip3 install -r requirements.txt



node_modules:
	npm install


dist:
	node esbuild.js


serve:
	node esbuild.js --serve


clean:
	rm -rf node_modules && rm -rf mumulib


tags:
	. mumulib/bin/activate && python3 python/mumulib/tags.py

