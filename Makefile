BLAST_DB_S3_BUCKET=ncbi-blast-databases
BLAST_DB_GS_BUCKET=blast-db
BLAST_DB_DIR=/mnt/blast-db

version: taxoniq/version.py
taxoniq/version.py: setup.py
	echo "__version__ = '$$(python3 setup.py --version)'" > $@

build:
	mkdir -p $(BLAST_DB_DIR)
	aws s3 cp s3://$(BLAST_DB_S3_BUCKET)/latest-dir .
	echo "blast_db_timestamp = '$$(cat latest-dir)'" > taxoniq/const.py
	aws s3 sync s3://$(BLAST_DB_S3_BUCKET)/$$(cat latest-dir)/ $(BLAST_DB_DIR)/ --exclude "*.nsq" --exclude "*.p*" --exclude "env_*" --exclude "patnt*" --exclude "refseq_rna*"
	python3 -c 'import logging; logging.basicConfig(level=logging.DEBUG); import taxoniq.build as tb; tb.build_trees()'

lint:
	flake8 $$(python3 setup.py --name)

test:
	python3 -m unittest discover --start-directory test --top-level-directory . --verbose

docs:
	sphinx-build docs docs/html

install: clean version build
	pip3 install wheel
	python3 setup.py bdist_wheel
	pip3 install --upgrade dist/*.whl

clean:
	-rm -rf build dist
	-rm -rf *.egg-info
	-rm -rf $$(python3 setup.py --name)/*.{zstd,marisa}

.PHONY: lint test docs install clean build

include common.mk
