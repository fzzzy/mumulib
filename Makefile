

.PHONY: all serve clean


all: node_modules build serve
	echo "Done"


venv:
	python3 -m venv venv
	. venv/bin/activate
	pip3 install -r requirements.txt



node_modules:
	npm install


dist:
	node esbuild.js


serve:
	node esbuild.js --serve


clean:
	rm -rf node_modules


tags:
	. venv/bin/activate && python3 python/mumulib/tags.py

