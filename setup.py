#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="taxoniq",
    version="0.0.6",
    url="https://github.com/chanzuckerberg/taxoniq",
    project_urls={
        "Documentation": "https://chanzuckerberg.github.io/taxoniq",
        "Source Code": "https://github.com/chanzuckerberg/taxoniq",
        "Issue Tracker": "https://github.com/chanzuckerberg/taxoniq/issues"
    },
    license="MIT License",
    author="Andrey Kislyuk",
    author_email="akislyuk@chanzuckerberg.com",
    description="Taxoniq: Taxon Information Query - fast, offline querying of NCBI Taxonomy and related data",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    install_requires=[
        "marisa-trie >= 0.7.5",
        "zstandard >= 0.15.1",
        "urllib3 >= 1.25.8",
        "taxoniq-accessions == 2021.2.9.post1",
        "taxoniq-accession-lengths == 2021.2.9",
        "taxoniq-accession-offsets == 2021.2.9"
    ],
    tests_require=["coverage", "flake8", "wheel"],
    packages=find_packages(exclude=["test"]),
    extras_require={
        # "nt_accession_db": []
        # "nr_accession_db": []
    },
    entry_points={
        "console_scripts": [
            "taxoniq=taxoniq.cli:cli"
        ],
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
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Software Development :: Libraries :: Python Modules"
    ]
)
