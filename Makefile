

all: build serve
	echo "Done"


build:
	node esbuild.js && cp src/index.html dist/index.html


serve:
	node esbuild.js --serve


