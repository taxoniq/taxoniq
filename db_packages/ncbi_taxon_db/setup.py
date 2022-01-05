#!/usr/bin/env python3

"""
[Taxoniq](https://github.com/chanzuckerberg/taxoniq) index for the NCBI Taxonomy database.

This package contains data from NCBI Taxonomy, NCBI GenBank, and NCBI RefSeq (Bethesda (MD): National Library of
Medicine (US), National Center for Biotechnology Information). These data are released into the public domain under the
[NCBI Public Domain Notice](https://github.com/chanzuckerberg/taxoniq/blob/main/LICENSE.NCBI).
"""

from setuptools import setup, find_packages

setup(
    name="ncbi-taxon-db",
    version="2021.11.16",
    install_requires=[
        "ncbi-refseq-accession-db == 2021.11.16",
        "ncbi-refseq-accession-lengths == 2021.11.16",
        "ncbi-refseq-accession-offsets == 2021.11.16"
    ],
    url="https://github.com/chanzuckerberg/taxoniq",
    license="MIT License",
    author="Andrey Kislyuk",
    author_email="akislyuk@chanzuckerberg.com",
    description="Taxoniq index for NCBI Taxonomy database",
    long_description=__doc__,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    include_package_data=True
)
