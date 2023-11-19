Changes for v1.0.1 (2023-11-19)
===============================

-  Update formatting of blast db volumes

Changes for v1.0.0 (2023-11-18)
===============================

-  Unvendor marisa-trie

-  Update data packages to version 2023-11-04

-  Bump major version to signify stable release series (no API changes)

Changes for v0.6.1 (2023-11-06)
===============================

-  Ensure input tax_id is stored as int

-  NCBI has switched from ftp to http; update URLs accordingly

Changes for v0.6.0 (2021-04-19)
===============================

-  Fix BLAST sequence DB trailing byte handling, timestamping

-  Fix sequence retrieval for single-volume databases

-  Update data packages to version 2021-04-10

Changes for v0.5.2 (2021-04-14)
===============================

Fix error handling

Changes for v0.5.1 (2021-04-14)
===============================

-  Fix CLI command naming issue in v0.5.0

Changes for v0.5.0 (2021-04-13)
===============================

-  CLI usability improvements: raise custom error when no value is found

-  Documentation improvements

Changes for v0.4.0 (2021-04-02)
===============================

-  Build and distribute ARM wheels (#9)

Changes for v0.3.4 (2021-04-01)
===============================

Repeat release GHA

Changes for v0.3.3 (2021-04-01)
===============================

-  Retry release GHA



Changes for v0.3.1 (2021-04-01)
===============================

-  Expose get_from_s3 via CLI

-  Documentation improvements

Changes for v0.3.0 (2021-03-27)
===============================

-  Use manylinux 2014 instead of 2.24 to build wheels

-  Documentation improvements

Changes for v0.2.0 (2021-03-26)
===============================

-  Refactor db package dependencies and release tooling to support
   automated releases of RefSeq and Genbank indexes

-  Update data packages to version 2021-03-25

Changes for v0.1.7 (2021-03-25)
===============================

Fix const file handling

Changes for v0.1.6 (2021-03-25)
===============================

Avoid github rate limit while polling

Changes for v0.1.5 (2021-03-25)
===============================

Fix const.py autogeneration

Changes for v0.1.4 (2021-03-25)
===============================

-  Clean build products before building

-  Update data packages to version 2021-03-23

-  Fixes for release script
