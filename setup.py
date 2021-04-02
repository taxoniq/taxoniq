#!/usr/bin/env python3

import glob
import itertools
import os.path
from setuptools import setup, find_packages, Extension

MARISA_ROOT_DIR = "marisa-trie/marisa-trie"
MARISA_SOURCE_DIR = os.path.join(MARISA_ROOT_DIR, "lib")
MARISA_INCLUDE_DIR = os.path.join(MARISA_ROOT_DIR, "include")
MARISA_FILES = [
    "marisa/*.cc",
    "marisa/grimoire.cc",
    "marisa/grimoire/io/*.cc",
    "marisa/grimoire/trie/*.cc",
    "marisa/grimoire/vector/*.cc",
]
MARISA_FILES[:] = itertools.chain(
    *(glob.glob(os.path.join(MARISA_SOURCE_DIR, path))
      for path in MARISA_FILES))

setup(
    name="taxoniq",
    version="0.4.0",
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
        "zstandard >= 0.15.1",
        "urllib3 >= 1.25.8",
        "ncbi-taxon-db >= 2021.3.25"
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
    libraries=[("libmarisa-trie", {
        "sources": MARISA_FILES,
        "include_dirs": [MARISA_SOURCE_DIR, MARISA_INCLUDE_DIR]
    })],
    ext_modules=[
        Extension("taxoniq.vendored.marisa_trie", [
            "marisa-trie/src/agent.cpp",
            "marisa-trie/src/base.cpp",
            "marisa-trie/src/iostream.cpp",
            "marisa-trie/src/key.cpp",
            "marisa-trie/src/keyset.cpp",
            "marisa-trie/src/marisa_trie.cpp",
            "marisa-trie/src/query.cpp",
            "marisa-trie/src/std_iostream.cpp",
            "marisa-trie/src/trie.cpp"
        ], include_dirs=[MARISA_INCLUDE_DIR])
    ],
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
