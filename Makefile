BLAST_DB_S3_BUCKET=ncbi-blast-databases
BLAST_DB_GS_BUCKET=blast-db

ifndef BLASTDB
$(error Please set BLASTDB)
endif

version: taxoniq/version.py
taxoniq/version.py: setup.py
	echo "__version__ = '$$(python3 setup.py --version)'" > $@

build:
	pip3 install --upgrade awscli marisa-trie zstandard urllib3 db_packages/*
	mkdir -p $(BLASTDB)
	aws s3 cp --no-sign-request s3://$(BLAST_DB_S3_BUCKET)/latest-dir .
	echo "blast_db_timestamp = '$$(cat latest-dir)'" > taxoniq/const.py
ifdef BLAST_DATABASES
	aws s3 sync --quiet --no-sign-request s3://$(BLAST_DB_S3_BUCKET)/$$(cat latest-dir)/ $(BLASTDB)/ --exclude "*" --include "Betacoronavirus*" --include "ref_viruses_rep_genomes*"
else
	aws s3 sync --no-sign-request s3://$(BLAST_DB_S3_BUCKET)/$$(cat latest-dir)/ $(BLASTDB)/ --exclude "*.nsq" --exclude "*.p*" --exclude "env_*" --exclude "patnt*" --exclude "refseq_rna*"
endif
	python3 -c 'import logging; logging.basicConfig(level=logging.DEBUG); import taxoniq.build as tb; tb.build_trees()'

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
	-rm -rf build dist
	-rm -rf *.egg-info
	-rm -rf $$(python3 setup.py --name)/*.{zstd,marisa}

.PHONY: lint test docs install clean build

include common.mk
