BLAST_DB_S3_BUCKET=ncbi-blast-databases
BLAST_DB_GS_BUCKET=blast-db

ifndef BLASTDB
$(error Please set BLASTDB)
endif

version: taxoniq/version.py
taxoniq/version.py: setup.py
	echo "__version__ = '$$(python3 setup.py --version)'" > $@

build-vendored-deps:
	cython -3 marisa-trie/src/*.pyx marisa-trie/src/*.pxd --cplus
	python3 setup.py build_clib
	python3 setup.py build_ext --inplace

build: build-vendored-deps
	pip3 install --upgrade awscli zstandard urllib3 db_packages/*
	mkdir -p $(BLASTDB)
	aws s3 cp --no-sign-request s3://$(BLAST_DB_S3_BUCKET)/latest-dir .
	echo "blast_db_timestamp = '$$(cat latest-dir)'" > taxoniq/const.py
ifdef BLAST_DATABASES
	aws s3 sync --quiet --no-sign-request s3://$(BLAST_DB_S3_BUCKET)/$$(cat latest-dir)/ $(BLASTDB)/ --exclude "*" $$(for db in $(BLAST_DATABASES); do echo --include "$$db*[!q]"; done)
else
	aws s3 sync --no-sign-request s3://$(BLAST_DB_S3_BUCKET)/$$(cat latest-dir)/ $(BLASTDB)/ --exclude "*.nsq" --exclude "*.p*" --exclude "env_*" --exclude "patnt*" --exclude "refseq_rna*"
endif
	python3 -c 'import logging; logging.basicConfig(level=logging.DEBUG); import taxoniq.build as tb; tb.build_trees()'
	if [[ $$CI ]]; then rm -rf $(BLASTDB); fi

lint:
	flake8 $$(python3 setup.py --name)

test:
	python3 -m unittest discover --start-directory test --top-level-directory . --verbose

docs:
	sphinx-build docs docs/html

install: clean version build
	pip3 install .
	pip3 install --upgrade db_packages/*

clean:
	-rm -rf build dist db_packages/*/{build,dist}
	-rm -rf *.egg-info
	-rm -rf db_packages/*/*/*.{zstd,marisa}

.PHONY: lint test docs install clean build build-vendored-deps

include common.mk
