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
- A stable, [well-documented](https://chanzuckerberg.github.io/taxoniq/#module-taxoniq), type-hinted Python API
  (Python 3.6 and higher is supported)
- Comprehensive testing and continuous integration
- An intuitive interface with useful defaults
- Compactness, readability, and extensibility

The Taxoniq package bundles an indexed, compressed copy of the
[NCBI taxonomy database files](https://ncbiinsights.ncbi.nlm.nih.gov/2018/02/22/new-taxonomy-files-available-with-lineage-type-and-host-information/),
the [NCBI RefSeq](https://www.ncbi.nlm.nih.gov/refseq/) nucleotide and protein accessions associated with each taxon,
the [WoL](https://biocore.github.io/wol/) kingdom-wide phylogenomic distance database, and relevant information from
other databases. Accessions which appear in the NCBI RefSeq BLAST databases are indexed so that
given a taxon ID, accession ID, or taxon name, you can quickly retrieve the taxon's rank, lineage, description,
citations, representative RefSeq IDs, LCA information, evolutionary distance, sequence (with a network call), and more,
as described in the **Cookbook** section below. Full [API documentation](https://chanzuckerberg.github.io/taxoniq/#module-taxoniq)
is available.

## Installation

    pip3 install taxoniq

Pre-built wheels are available for Python 3.5+ on Linux and MacOS. On MacOS 11 Big Sur, Pip 20.3+ is required to install
pre-built wheels (you can check your version with `pip3 --version` and upgrade with `pip3 install --upgrade pip`).

## Synopsis

```python
>>> import taxoniq
>>> t = taxoniq.Taxon(9606)
>>> t.scientific_name
'Homo sapiens'
>>> t.common_name
'human'

>>> t.ranked_lineage
[taxoniq.Taxon(9606), taxoniq.Taxon(9605), taxoniq.Taxon(9604), taxoniq.Taxon(9443),
 taxoniq.Taxon(40674), taxoniq.Taxon(7711), taxoniq.Taxon(33208), taxoniq.Taxon(2759)]
>>> len(t.lineage)
32
>>> [(t.rank.name, t.scientific_name) for t in t.ranked_lineage]
[('species', 'Homo sapiens'), ('genus', 'Homo'), ('family', 'Hominidae'), ('order', 'Primates'),
 ('class', 'Mammalia'), ('phylum', 'Chordata'), ('kingdom', 'Metazoa'), ('superkingdom', 'Eukaryota')]
>>> [(c.rank.name, c.common_name) for c in t.child_nodes]
[('subspecies', 'Neandertal'), ('subspecies', 'Denisova hominin')]

>>> t.refseq_representative_genome_accessions[:10]
[taxoniq.Accession('NC_000001.11'), taxoniq.Accession('NC_000002.12'), taxoniq.Accession('NC_000003.12'),
 taxoniq.Accession('NC_000004.12'), taxoniq.Accession('NC_000005.10'), taxoniq.Accession('NC_000006.12'),
 taxoniq.Accession('NC_000007.14'), taxoniq.Accession('NC_000008.11'), taxoniq.Accession('NC_000009.12'),
 taxoniq.Accession('NC_000010.11')]

>>> t.url
'https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?mode=Info&id=9606'

# Wikidata provides structured links to many databases about taxa represented on Wikipedia
>>> t.wikidata_url
'https://www.wikidata.org/wiki/Q15978631'
```

```
>>> t2 = taxoniq.Taxon(scientific_name="Bacillus anthracis")
>>> t2.description
'<p class="mw-empty-elt"> </p> <p class="mw-empty-elt"> </p> <p><i><b>Bacillus anthracis</b></i>
 is the agent of anthrax—a common disease of livestock and, occasionally, of humans—and the only
 obligate pathogen within the genus <i>Bacillus</i>. This disease can be classified as a zoonosis,
 causing infected animals to transmit the disease to humans. <i>B. anthracis</i> is a Gram-positive,
 endospore-forming, rod-shaped bacterium, with a width of 1.0–1.2 µm and a length of 3–5&#160;µm.
 It can be grown in an ordinary nutrient medium under aerobic or anaerobic conditions.</p>
 <p>It is one of few bacteria known to synthesize a protein capsule (poly-D-gamma-glutamic acid).
 Like <i>Bordetella pertussis</i>, it forms a calmodulin-dependent adenylate cyclase exotoxin known
 as anthrax edema factor, along with anthrax lethal factor. It bears close genotypic and phenotypic
 resemblance to <i>Bacillus cereus</i> and <i>Bacillus thuringiensis</i>. All three species share
 cellular dimensions and morphology</p>...'
```

```python
>>> t3 = taxoniq.Taxon(accession_id="NC_000913.3")
>>> t3.scientific_name
'Escherichia coli str. K-12 substr. MG1655"'
>>> t3.parent.parent.common_name
'E. coli'
>>> t3.refseq_representative_genome_accessions[0].length
4641652

# The get_from_s3() method is the only command that will trigger a network call.
>>> seq = t3.refseq_representative_genome_accessions[0].get_from_s3().read()
>>> len(seq)
4641652
>>> seq[:64]
b'AGCTTTTCATTCTGACTGCAACGGGCAATATGTCTCTGTGTGGATTAAAAAAAGAGTGTCTGAT'
```

## Retrieving sequences

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
```python
with taxoniq.Accession("NC_000913.3").get_from_s3() as fh:
    fh.read()
```
For brevity, you can use [urllib3.response.HTTPResponse.stream](https://urllib3.readthedocs.io/en/latest/advanced-usage.html)
instead of `read(...)` to avoid holding the entire sequence in memory:
```python
with taxoniq.Accession("NC_000913.3").get_from_s3() as fh:
    for chunk in fh.stream():
        sys.stdout.buffer.write(chunk)
```

To retrieve many sequences quickly, you may want to use a threadpool to open multiple network connections at once:
```python
from concurrent.futures import ThreadPoolExecutor
def fetch_seq(accession):
    seq = accession.get_from_s3().read()
    return (accession, seq)

taxon = taxoniq.Taxon(scientific_name="Apis mellifera")
for accession, seq in ThreadPoolExecutor().map(fetch_seq, taxon.refseq_representative_genome_accessions):
    print(accession, len(seq))
```
This operation is also available in the CLI, as described below.

## Command-line interface
`pip3 install taxoniq` installs a command-line utility, `taxoniq`, which can be used to perform many of the same
functions provided by the Python API:
```
>taxoniq child_nodes --taxon-id 2 --output-format '{tax_id}: {scientific_name}'
[
    "1224: Proteobacteria",
    "2323: Bacteria incertae sedis",
    "32066: Fusobacteria",
    "40117: Nitrospirae",
    "48479: environmental samples",
    "49928: unclassified Bacteria",
    "57723: Acidobacteria",
    "68297: Dictyoglomi",
    "74152: Elusimicrobia",
    "200783: Aquificae",
    "200918: Thermotogae",
    "200930: Deferribacteres",
    "200938: Chrysiogenetes",
    "200940: Thermodesulfobacteria",
    "203691: Spirochaetes",
    "508458: Synergistetes",
    "1783257: PVC group",
    "1783270: FCB group",
    "1783272: Terrabacteria group",
    "1802340: Nitrospinae/Tectomicrobia group",
    "1930617: Calditrichaeota",
    "2138240: Coprothermobacterota",
    "2498710: Caldiserica/Cryosericota group",
    "2698788: Candidatus Krumholzibacteriota",
    "2716431: Coleospermum",
    "2780997: Vogosella"
]
```
See `taxoniq --help` for full details.
#### Retrieving sequences using the CLI
To retrieve an individual sequence in FASTA format given an accession ID, use `taxoniq get_from_s3 --accession-id ACCESSION_ID`.

To retrieve multiple sequences in FASTA format, use `--accession-id -` and pass the IDs on standard input, one per line:
```
taxoniq refseq_representative_genome_accessions --scientific-name="Apis mellifera" | jq -r .[] | taxoniq get_from_s3 --accession-id -
```

## Using the nr/nt databases
Because of their size, taxoniq wheels with indexes of the NT (GenBank Non-redundant nucleotide) BLAST database are
distributed on GitHub instead of PyPI. After running `pip3 install taxoniq`, you can install the NT indexes as follows:

- Navigate to https://github.com/chanzuckerberg/taxoniq/releases/latest
- In the "Assets" section, for each link that starts with "ncbi_genbank" and ends with ".whl":
  - Right-click on the asset link, and click "Copy link address"
  - Run `pip3 install --upgrade <PASTED LINK ADDRESS>`

The NT index packages also contain indexes for the RefSeq representative genomes and Betacoronavirus accessions (meaning
they are are superset of the PyPI packages).

## Streaming CLI I/O
The `taxoniq` command-line interface can take streaming input from stdin and produce streaming output on stdout. This
allows the amortization of startup and index load time and efficient operation as part of shell pipelines.

The following
example shows the pipelined operation of [fastp](https://github.com/OpenGene/fastp),
[kraken2](https://github.com/DerrickWood/kraken2/wiki), and taxoniq to annotate hits found in a Betacoronavirus sample:
```
in progress
```
<!--
fastp --thread $KRAKEN2_NUM_THREADS --low_complexity_filter -i R1.fastq.gz -I R2.fastq.gz -o filtered.R1.fastq.gz -O filtered.R2.fastq.gz

kraken2 --paired nohuman_1.fastq nohuman_2.fastq --classified-out 'classified#.fastq' | taxoniq
-->

## Cookbook
In progress

## Links
* [Project home page (GitHub)](https://github.com/chanzuckerberg/taxoniq)
* [Documentation](https://chanzuckerberg.github.io/taxoniq/)
* [Package distribution (PyPI)](https://pypi.python.org/pypi/taxoniq)
* [Change log](https://github.com/chanzuckerberg/taxoniq/blob/master/Changes.md)

## License
Taxoniq software is licensed under the terms of the [MIT License](LICENSE).

Distributions of this package contain data from
[NCBI Taxonomy, NCBI GenBank, and NCBI RefSeq](https://www.ncbi.nlm.nih.gov/) (Bethesda (MD): National Library of
Medicine (US), National Center for Biotechnology Information). These data are released into the public domain under the
[NCBI Public Domain Notice](LICENSE.NCBI).

Distributions of this package contain text excerpts from Wikipedia licensed under the terms of the
[CC-BY-SA License](LICENSE.WIKIPEDIA).

## Bugs
Please report bugs, issues, feature requests, etc. on [GitHub](https://github.com/chanzuckerberg/taxoniq/issues).
