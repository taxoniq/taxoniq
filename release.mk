SHELL=/bin/bash -eo pipefail

release-major:
	$(eval export TAG=$(shell git describe --tags --match 'v*.*.*' | perl -ne '/^v(\d+)\.(\d+)\.(\d+)/; print "v@{[$$1+1]}.0.0"'))
	$(MAKE) release

release-minor:
	$(eval export TAG=$(shell git describe --tags --match 'v*.*.*' | perl -ne '/^v(\d+)\.(\d+)\.(\d+)/; print "v$$1.@{[$$2+1]}.0"'))
	$(MAKE) release

release-patch:
	$(eval export TAG=$(shell git describe --tags --match 'v*.*.*' | perl -ne '/^v(\d+)\.(\d+)\.(\d+)/; print "v$$1.$$2.@{[$$3+1]}"'))
	$(MAKE) release

check-release-deps:
	@if ! git diff --cached --exit-code; then echo "Please commit staged files before proceeding"; exit 1; fi
	@if ! type -P pandoc; then echo "Please install pandoc"; exit 1; fi
	@if ! type -P sponge; then echo "Please install moreutils"; exit 1; fi
	@if ! type -P http; then echo "Please install httpie"; exit 1; fi
	@if ! type -P gh; then echo "Please install gh"; exit 1; fi
	@if ! type -P twine; then echo "Please install twine"; exit 1; fi

release: check-release-deps
	git pull
	@if [[ -z $$TAG ]]; then echo "Use release-{major,minor,patch}"; exit 1; fi
	git clean -x --force $$(python3 setup.py --name)
	sed -i -e "s/version=\([\'\"]\)[0-9]*\.[0-9]*\.[0-9]*/version=\1$${TAG:1}/" setup.py
	$(MAKE) version
	git add setup.py taxoniq/version.py
	TAG_MSG=$$(mktemp); \
	    echo "# Changes for ${TAG} ($$(date +%Y-%m-%d))" > $$TAG_MSG; \
	    git log --pretty=format:%s $$(git describe --abbrev=0)..HEAD >> $$TAG_MSG; \
	    $${EDITOR:-emacs} $$TAG_MSG; \
	    if [[ -f Changes.md ]]; then cat $$TAG_MSG <(echo) Changes.md | sponge Changes.md; git add Changes.md; fi; \
	    if [[ -f Changes.rst ]]; then cat <(pandoc --from markdown --to rst $$TAG_MSG) <(echo) Changes.rst | sponge Changes.rst; git add Changes.rst; fi; \
	    git commit -m ${TAG}; \
	    git tag --annotate --file $$TAG_MSG ${TAG}
	git push --follow-tags
	gh release create ${TAG} dist/*.whl --notes="$$(git tag --list ${TAG} -n99 | perl -pe 's/^\S+\s*// if $$. == 1' | sed 's/^\s\s\s\s//')"
	$(MAKE) release-pypi
	$(MAKE) release-docs

release-db-packages: check-release-deps
	git pull
	sed -i -e "s/20[0-9][0-9].[0-9]*.[0-9]*/$$(cat latest-dir | cut -f 1-3 -d - | sed -e 's/-/./g' -e 's/\.0/\./')/" setup.py db_packages/*/setup.py
	git add setup.py db_packages/*/setup.py
	git commit -m "Update data packages to version $$(cat latest-dir | cut -f 1-3 -d -)"
	git push
	-rm -rf db_packages/*/build db_packages/*/dist
	for p in db_packages/*; do (cd $$p; python3 setup.py bdist_wheel); done
	twine upload db_packages/ncbi_taxon_db/dist/*.whl db_packages/ncbi_refseq_*/dist/*.whl --verbose
	gh release upload v$$(python3 setup.py --version) db_packages/ncbi_genbank_*/dist/*.whl

release-pypi:
	python3 setup.py sdist
	twine upload dist/*.tar.gz dist/*.whl --verbose

release-docs:
	$(MAKE) docs
	-git branch -D gh-pages
	git checkout -B gh-pages-stage
	touch docs/html/.nojekyll
	git add --force docs/html
	git commit -m "Docs for ${TAG}"
	git push --force origin $$(git subtree split --prefix docs/html --branch gh-pages):refs/heads/gh-pages
	git checkout -

.PHONY: release* check-release-deps
