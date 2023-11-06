BLAST_DB_S3_BUCKET=ncbi-blast-databases
BLAST_DB_GS_BUCKET=blast-db
TAXDUMP_URL=https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz
NCBI_BLASTPLUS_URL=https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/ncbi-blast-2.15.0+-x64-linux.tar.gz

ifndef BLASTDB
$(error Please set BLASTDB)
endif

version: taxoniq/version.py
taxoniq/version.py: setup.py
	echo "__version__ = '$$(python3 setup.py --version)'" > $@

get-wikipedia-extracts:
	python3 -m taxoniq.build wikipedia-extracts

build-vendored-deps:
	if [[ ! -d marisa-trie/marisa-trie ]]; then git submodule update --init --recursive; fi
	pip3 install cython
	cython -3 marisa-trie/src/*.pyx marisa-trie/src/*.pxd --cplus
	python3 setup.py build_clib
	python3 setup.py build_ext --inplace

build: version build-vendored-deps
	if ! type blastdbcmd; then curl $(NCBI_BLASTPLUS_URL) | tar -xvz; fi
	if [[ ! -e wikipedia_extracts.json ]]; then $(MAKE) get-wikipedia-extracts; fi
	pip3 install --upgrade awscli zstandard urllib3 twine db_packages/ncbi_taxon_db db_packages/ncbi_refseq_accession_*
	if [[ ! -f nodes.dmp ]] || [[ $$(($$(date +%s) - $$(stat --format %Y nodes.dmp))) -gt $$((60*60*24)) ]]; then curl $(TAXDUMP_URL) | tar -xvz; fi
	mkdir -p $(BLASTDB)
	aws s3 cp --no-sign-request s3://$(BLAST_DB_S3_BUCKET)/latest-dir .
ifdef BLAST_DATABASES
	aws s3 sync --quiet --size-only --no-sign-request s3://$(BLAST_DB_S3_BUCKET)/$$(cat latest-dir)/ $(BLASTDB)/ --exclude "*" $$(for db in $(BLAST_DATABASES); do echo --include "$$db*"; done)
else
	aws s3 sync --size-only --no-sign-request s3://$(BLAST_DB_S3_BUCKET)/$$(cat latest-dir)/ $(BLASTDB)/ --exclude "*.p*" --exclude "env_*" --exclude "patnt*" --exclude "refseq_rna*"
endif
	python3 -m taxoniq.build trees
	if [[ $$CI ]]; then rm -rf $(BLASTDB); fi

lint:
	ruff taxoniq

test:
	python3 -m unittest discover --start-directory test --top-level-directory . --verbose

docs:
	pip3 install sphinx guzzle_sphinx_theme m2r2==0.2.7
	sphinx-build docs docs/html

install: version build
	pip3 install .
	pip3 install --upgrade db_packages/ncbi_taxon_db db_packages/ncbi_refseq_accession_*

clean:
	-rm -rf build dist db_packages/*/{build,dist}
	-rm -rf *.egg-info
	-rm -rf db_packages/*/*/*.{zstd,marisa}

.PHONY: lint test docs install clean build build-vendored-deps

include release.mk
