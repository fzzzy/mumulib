

all: install build serve
	echo "Done"


install:
	npm install


build:
	node esbuild.js && cp src/index.html dist/index.html


serve:
	node esbuild.js --serve


