BLAST_DB_S3_BUCKET=ncbi-blast-databases
BLAST_DB_GS_BUCKET=blast-db
TAXDUMP_URL=https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz
# Note: The newest BLAST+ version is only required for building, not for using the indexes
NCBI_BLASTPLUS_URL=https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/ncbi-blast-2.15.0+-x64-linux.tar.gz
LAUNCHPAD_BLASTPLUS_URL=https://launchpad.net/ubuntu/+archive/primary/+files/ncbi-blast+_2.16.0+ds-6_amd64.deb
BLAST_DATABASES=ref_viruses_rep_genomes ref_prok_rep_genomes ref_euk_rep_genomes Betacoronavirus core_nt

.DEFAULT_GOAL := build

get-wikipedia-extracts:
	python3 -m taxoniq.build wikipedia-extracts

build:
	rm -rf dist
	python3 -m build

build-indexes:
	@test -n "$(BLASTDB)" || { echo "Please set BLASTDB"; exit 1; }
	pip3 install --upgrade -e . awscli zstandard urllib3 twine db_packages/ncbi_taxon_db db_packages/ncbi_refseq_accession_*
	if ! type blastdbcmd; then sudo apt-get install -y ncbi-blast+; curl -L -O $(LAUNCHPAD_BLASTPLUS_URL); sudo dpkg -i $$(basename $(LAUNCHPAD_BLASTPLUS_URL)); fi
	if [[ ! -e wikipedia_extracts.json ]]; then $(MAKE) get-wikipedia-extracts; fi
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
	ruff check taxoniq scripts

test:
	python3 -m unittest discover --start-directory test --top-level-directory . --verbose

docs:
	pip3 install -e '.[docs]'
	sphinx-build docs docs/html

install: build
	pip3 install --upgrade dist/*.whl

install-db-packages: build-indexes
	pip3 install --upgrade db_packages/ncbi_taxon_db db_packages/ncbi_refseq_accession_*

clean:
	-rm -rf build dist db_packages/*/{build,dist}
	-rm -rf *.egg-info
	-rm -rf db_packages/*/*/*.{zstd,marisa}

.PHONY: lint test docs install install-db-packages clean build build-indexes get-wikipedia-extracts

include common.mk
include release.mk
