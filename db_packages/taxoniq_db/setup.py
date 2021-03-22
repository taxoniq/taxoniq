#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="taxoniq-db",
    version="2021.3.20",
    install_requires=[
        "taxoniq-accessions == 2021.3.20",
        "taxoniq-accession-lengths == 2021.3.20",
        "taxoniq-accession-offsets == 2021.3.20"
    ],
    url="https://github.com/chanzuckerberg/taxoniq",
    license="MIT License",
    author="Andrey Kislyuk",
    author_email="akislyuk@chanzuckerberg.com",
    description="Taxoniq index for NCBI Taxonomy database",
    packages=find_packages(),
    include_package_data=True
)
