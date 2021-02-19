Taxoniq: Taxon Information Query - fast, offline querying of NCBI Taxonomy and related data
===========================================================================================

Taxoniq is a Python and command-line interface to the
[NCBI Taxonomy database](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7408187/) and selected data sources that
cross-reference it.

Taxoniq's features include:

- Pre-computed indexes updated monthly from NCBI, [WoL](https://biocore.github.io/wol/) and cross-referenced databases
- Offline operation: all indexes are bundled with the package; no network calls are made when querying taxon information
  (separately, Taxoniq can fetch the nucleotide or protein sequences over the network given a taxon or accession - see
  **Retrieving sequences** below)
- A CLI capable of JSON I/O, batch processing and streaming of inputs for ease of use and pipelining in shell scripts
- A stable, well-documented, type-hinted Python API (Python 3.6 and higher is supported)
- Comprehensive testing and continuous integration
- An intuitive interface with useful defaults
- Compactness, readability, and extensibility

The Taxoniq package bundles an indexed, compressed copy of the
[NCBI taxonomy database files](https://ncbiinsights.ncbi.nlm.nih.gov/2018/02/22/new-taxonomy-files-available-with-lineage-type-and-host-information/),
the [NCBI RefSeq](https://www.ncbi.nlm.nih.gov/refseq/) nucleotide and protein accessions associated with each taxon,
the [WoL](https://biocore.github.io/wol/) kingdom-wide phylogenetic distance database, and relevant information from
other databases. Accessions which appear in the NCBI RefSeq BLAST databases are indexed so that
given a taxon ID, accession ID, or taxon name, you can quickly retrieve the taxon's rank, lineage, description,
citations, representative RefSeq IDs, LCA information, evolutionary distance, sequence (with a network call), and more,
as described in the **Cookbook** section below.

# Installation

    pip3 install taxoniq

# Synopsis

```
t = taxoniq.Taxon(9606)
assert t.scientific_name == "Homo sapiens"
assert t.common_name == "human"
assert t.ranked_lineage == [taxoniq.Taxon(scientific_name='Homo sapiens'),
                            taxoniq.Taxon(scientific_name='Homo'),
                            taxoniq.Taxon(scientific_name='Hominidae'),
                            taxoniq.Taxon(scientific_name='Primates'),
                            taxoniq.Taxon(scientific_name='Mammalia'),
                            taxoniq.Taxon(scientific_name='Chordata'),
                            taxoniq.Taxon(scientific_name='Metazoa'),
                            taxoniq.Taxon(scientific_name='Eukaryota')]
t.refseq_representative_genome_accessions
# ['NT_113888.1', ..., 'NC_000024.10', 'NC_000023.11', 'NC_000022.11', 'NC_000021.9', 'NC_000020.11', 'NC_000019.10',
#  'NC_000018.10', 'NC_000017.11', 'NC_000016.10', 'NC_000015.10', 'NC_000014.9', 'NC_000013.11', 'NC_000012.12',
#  'NC_000011.10', 'NC_000010.11', 'NC_000009.12', 'NC_000008.11', 'NC_000007.14', 'NC_000006.12', 'NC_000005.10',
#  'NC_000004.12', 'NC_000003.12', 'NC_000002.12', 'NC_000001.11', ..., 'NW_021159987.1']

t2 = taxoniq.Taxon(accession_id="NC_000913.3")
assert t2 == taxoniq.Taxon(scientific_name="Escherichia coli str. K-12 substr. MG1655")
assert t2.parent.parent.common_name == "E. coli"
```

# Retrieving sequences

Mirrors of the NCBI BLAST databases are maintained on [AWS S3](https://registry.opendata.aws/ncbi-blast-databases/)
(`s3://ncbi-blast-databases`) and Google Storage (`gs://blast-db`). This is a key resource, since S3 and GS have
superior bandwidth and throughput compared to the NCBI FTP server, so range requests can be used to retrieve individual
sequences from the database files without downloading and keeping a copy of the whole database.

The Taxoniq PyPI distribution (the package you install using `pip3 install taxoniq`) indexes accessions for the
following NCBI BLAST databases:

- Refseq viruses representative genomes (`ref_viruses_rep_genomes`) (nucleotide)
- Refseq prokaryote representative genomes (contains refseq assembly) (`ref_prok_rep_genomes`) (nucleotide)
- RefSeq Eukaryotic Representative Genome Database (`ref_euk_rep_genomes`) (nucleotide)
- Betacoronavirus (nucleotide)

Given an accession ID, Taxoniq can issue a single HTTP request and return a file-like object streaming the nucleotide
sequence for this accession from the S3 or GS mirror as follows:
```
with taxoniq.Accession("NC_000913.3").get_from_s3() as fh:
     fh.read()
```

To retrieve many sequences quickly, you may want to use a threadpool to open multiple network connections at once:
```
from concurrent.futures import ThreadPoolExecutor
def fetch_seq(accession_id):
    accession = taxoniq.Accession(accession_id)
    seq = accession.get_from_s3().read()
    return (accession, seq)

taxon = taxoniq.Taxon(scientific_name="Apis mellifera")
for accession, seq in ThreadPoolExecutor().map(fetch_seq, taxon.refseq_representative_genome_accessions):
    print(accession, len(seq))
```

# Using the nr/nt databases
In progress

# Cookbook
In progress

# Links

# License
Taxoniq software is licensed under the terms of the [MIT License](LICENSE).

Distributions of this package contain data from the
[National Center for Biotechnology Information](https://www.ncbi.nlm.nih.gov/) released into the public domain under the
[NCBI Public Domain Notice](LICENSE.NCBI).

Distributions of this package contain text excerpts from Wikipedia licensed under the terms of the
[CC-BY-SA License](LICENSE.WIKIPEDIA).

# Bugs
Please report bugs, issues, feature requests, etc. on [GitHub](https://github.com/kislyuk/argcomplete/issues).
