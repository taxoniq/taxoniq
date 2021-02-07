#!/usr/bin/env python3

import os
from setuptools import setup, find_packages

install_requires = [line.rstrip() for line in open(os.path.join(os.path.dirname(__file__), "requirements.txt"))]
tests_require = ["coverage", "flake8", "wheel"]

setup(
    name="taxoniq",
    version="0.0.1",
    url="https://github.com/chanzuckerberg/taxoniq",
    license="MIT License",
    author="Andrey Kislyuk",
    author_email="akislyuk@chanzuckerberg.com",
    description="Taxoniq: Taxon Information Query - fast, offline querying of NCBI Taxonomy and related data",
    long_description=open("README.md").read(),
    install_requires=install_requires,
    tests_require=tests_require,
    packages=find_packages(exclude=["test"]),
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
