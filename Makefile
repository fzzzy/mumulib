

all: install build serve
	echo "Done"


install:
	npm install


build:
	node esbuild.js


serve:
	node esbuild.js --serve


