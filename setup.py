#!/usr/bin/env python3

import glob
import itertools
import os.path

from setuptools import Extension, find_packages, setup

setup(
    name="taxoniq",
    version="1.0.1",
    url="https://github.com/chanzuckerberg/taxoniq",
    project_urls={
        "Documentation": "https://chanzuckerberg.github.io/taxoniq",
        "Source Code": "https://github.com/chanzuckerberg/taxoniq",
        "Issue Tracker": "https://github.com/chanzuckerberg/taxoniq/issues",
    },
    license="MIT License",
    author="Andrey Kislyuk",
    author_email="akislyuk@chanzuckerberg.com",
    description="Taxoniq: Taxon Information Query - fast, offline querying of NCBI Taxonomy and related data",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    install_requires=[
        "marisa-trie >= 1.1.0",
        "zstandard >= 0.21.0",
        "urllib3 >= 1.26.5",
        "ncbi-taxon-db >= 2023.11.4",
    ],
    tests_require=["coverage", "flake8", "wheel"],
    packages=find_packages(exclude=["test"]),
    extras_require={
        # "nt_accession_db": []
        # "nr_accession_db": []
    },
    entry_points={
        "console_scripts": ["taxoniq=taxoniq.cli:cli"],
    },
    platforms=["MacOS X", "Posix"],
    include_package_data=True,
    test_suite="test",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
