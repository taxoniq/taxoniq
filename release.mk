# Project-specific releases; library releases are handled by common.mk and GitHub Actions.

check-db-release-deps:
	@if ! git diff --cached --exit-code; then echo "Please commit staged files before proceeding"; exit 1; fi
	@if ! type -P gh; then echo "Please install gh"; exit 1; fi
	@if ! type -P twine; then echo "Please install the release extra"; exit 1; fi

release-db-packages: check-db-release-deps
	git pull
	python3 scripts/update_db_versions.py latest-dir
	git add pyproject.toml db_packages/*/pyproject.toml db_packages/*/*/version.py
	git commit -m "Update data packages for $$(cat latest-dir)"
	git push
	-rm -rf db_packages/*/build db_packages/*/dist
	for p in db_packages/*; do python3 -m build --wheel $$p; done
	twine upload db_packages/ncbi_taxon_db/dist/*.whl db_packages/ncbi_refseq_*/dist/*.whl --verbose
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
