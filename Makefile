version: taxoniq/version.py
taxoniq/version.py: setup.py
	echo "__version__ = '$$(python3 setup.py --version)'" > $@

build:
	python3 -c 'import taxoniq.build as tb; tb.build_trees()'

lint:
	flake8 $$(python3 setup.py --name)

test: lint
	coverage run --source=$$(python3 setup.py --name) ./test/test.py -v

docs:
	sphinx-build docs docs/html

install: clean version
	pip install wheel
	python setup.py bdist_wheel
	pip install --upgrade dist/*.whl

clean:
	-rm -rf build dist
	-rm -rf *.egg-info

.PHONY: lint test docs install clean

include common.mk
