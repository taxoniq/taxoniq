# Project-specific releases; library releases are handled by common.mk and GitHub Actions.
# release-db-packages builds the data wheels locally and attaches them to a db-YYYY.M.D GitHub release; the
# workflow_dispatch trigger in .github/workflows/release.yml then publishes them to PyPI with trusted publishing.

check-db-release-deps:
	@if ! git diff --cached --exit-code; then echo "Please commit staged files before proceeding"; exit 1; fi
	@if ! type -P gh; then echo "Please install gh"; exit 1; fi
	@if [[ ! -f latest-dir ]]; then echo "latest-dir not found; run make build-indexes first"; exit 1; fi
	@if ! python3 -c 'import build, tomlkit, packaging' 2>/dev/null; then echo "Please install the release extra"; exit 1; fi

release-db-packages: check-db-release-deps
	git pull
	python3 scripts/update_db_versions.py latest-dir
	git add pyproject.toml db_packages/*/pyproject.toml db_packages/*/*/version.py
	git commit -m "Update data packages for $$(cat latest-dir)"
	git push
	-rm -rf db_packages/*/build db_packages/*/dist
	for p in db_packages/*; do python3 -m build --wheel $$p; done
	DB_TAG=$$(perl -ne 'if (/^(\d+)-(\d+)-(\d+)/) { print "db-" . ($$1+0) . "." . ($$2+0) . "." . ($$3+0); exit }' latest-dir); \
	    gh release create $$DB_TAG --target $$(git rev-parse HEAD) --latest=false --title "Data packages $$DB_TAG" \
	        --notes "Indexes built from NCBI BLAST databases $$(cat latest-dir)." \
	        db_packages/ncbi_taxon_db/dist/*.whl db_packages/ncbi_refseq_*/dist/*.whl && \
	    echo "To publish to PyPI, run: gh workflow run release.yml --ref main -f db-release-tag=$$DB_TAG"
	gh release upload $$(git describe --tags --abbrev=0 --match 'v*.*.*') db_packages/ncbi_genbank_*/dist/*.whl

release-docs:
	$(MAKE) docs
	-git branch -D gh-pages
	git checkout -B gh-pages-stage
	touch docs/html/.nojekyll
	git add --force docs/html
	git commit -m "Docs for ${TAG}"
	git push --force origin $$(git subtree split --prefix docs/html --branch gh-pages):refs/heads/gh-pages
	git checkout -

.PHONY: check-db-release-deps release-db-packages release-docs
