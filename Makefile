

all: node_modules build serve
	echo "Done"


node_modules:
	npm install


build:
	node esbuild.js


serve:
	node esbuild.js --serve


clean:
	rm -rf node_modules


