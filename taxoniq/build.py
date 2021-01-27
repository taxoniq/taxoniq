import os
import sys
import inspect
import collections
import subprocess
import enum
import gzip
import logging
import io

import marisa_trie
import zstandard

logger = logging.getLogger(__name__)

Rank = enum.Enum(
    "rank",
    ("biotype clade class cohort family forma forma_specialis genotype genus infraclass infraorder isolate kingdom "
     "morph order parvorder pathogroup phylum section series serogroup serotype species species_group species_subgroup "
     "strain subclass subcohort subfamily subgenus subkingdom suborder subphylum subsection subspecies subtribe "
     "subvariety superclass superfamily superkingdom superorder superphylum tribe varietas no_rank")
)

class TaxDumpReader:
    def __init__(self):
        self.fh = open(self.table_name + ".dmp")

    def __iter__(self):
        def cast(field, value):
            value = value.rstrip("\t|")
            if field[0] == "rank":
                return Rank[value.replace(" ", "_")].value
            if field[1] == int and value == "":
                return None
            return field[1](value)

        for row in self.fh:
            yield {self.fields[i][0]: cast(self.fields[i], value) for i, value in enumerate(row.strip().split("\t|\t"))}


class NodesReader(TaxDumpReader):
    table_name = "nodes"
    fields = [
        ("tax_id", int, "node id in GenBank taxonomy database"),
        ("parent", int, "parent node id in GenBank taxonomy database"),
        ("rank", str, "rank of this node (superkingdom, kingdom, ...)", Rank),
        ("embl_code", str, "locus-name prefix; not unique", enum.Enum),
        ("division_id", int, "see division.dmp file"),
        ("inherited_div", int, "flag  (1 or 0); 1 if node inherits division from parent"),
        ("genetic_code", int, "see gencode.dmp file"),
        ("inherited_GC", int, "flag  (1 or 0); 1 if node inherits genetic code from parent"),
        ("mitochondrial_genetic_code", int, "see gencode.dmp file"),
        ("inherited_MGC", int, "flag  (1 or 0); 1 if node inherits mitochondrial gencode from parent"),
        ("GenBank_hidden", int, "flag (1 or 0); 1 if name is suppressed in GenBank entry lineage"),
        ("hidden_subtree_root", int, "flag (1 or 0); 1 if this subtree has no sequence data yet"),
        ("comments", str, "free-text comments and citations"),
        ("plastid_genetic_code", int, "see gencode.dmp file"),
        ("inherited_PGC_flag", int, "flag (1 or 0); 1 if node inherits plastid gencode from parent"),
        ("specified_species", int, "flag (1 or 0); 1 if species in the node's lineage has formal name"),
        ("hydrogenosome_genetic_code", int, "see gencode.dmp file"),
        ("inherited_HGC", int, "flag (1 or 0); 1 if node inherits hydrogenosome gencode from parent")
    ]


class TaxonomyNamesReader(TaxDumpReader):
    """
    See https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3245000/
    """
    table_name = "names"
    fields = [
        ("tax_id", int, "the id of node associated with this name"),
        ("name", str, "name itself"),
        ("unique_name", str, "the unique variant of this name if name not unique"),
        ("name_class", str, "(synonym, common name, ...)", enum.Enum)
    ]


class DivisionsReader(TaxDumpReader):
    table_name = "division"
    fields = [
        ("division_id", int, "taxonomy database division id"),
        ("division_code", str, "GenBank division code (three characters) e.g. BCT, PLN, VRT, MAM, PRI.."),
        ("division_name", str),
        ("comments", str)
    ]

class GeneticCodeReader(TaxDumpReader):
    table_name = "gencode"
    fields = [
        ("genetic_code", int, "GenBank genetic code id"),
        ("abbreviation", str, "genetic code name abbreviation"),
        ("name", str, "genetic code name"),
        ("cde", str, "translation table for this genetic code"),
        ("starts", str, "start codons for this genetic code")
    ]

class DeletedNodesReader(TaxDumpReader):
    table_name = "delnodes"
    fields = [
        ("tax_id", int, "deleted node id")
    ]


class MergedNodesReader(TaxDumpReader):
    table_name = "merged"
    fields = [
        ("old_tax_id", int, "id of nodes which has been merged"),
        ("new_tax_id", int, "id of nodes which is result of merging")
    ]


class CitationsReader(TaxDumpReader):
    table_name = "citations"
    fields = [
        ("cit_id", int, "the unique id of citation"),
        ("cit_key", str, "citation key"),
        ("medline_id", int, "unique id in MedLine database (0 if not in MedLine)"),
        ("pubmed_id", int, "unique id in PubMed database (0 if not in PubMed)"),
        ("url", str, "URL associated with citation"),
        ("text", str, """any text (usually article name and authors); The following characters are escaped in this text
                         by a backslash: newline (appear as "\n"), tab character ("\t"), double quotes ('\"'),
                         backslash character ("\\")."""),
        ("taxid_list", str, "list of node ids separated by a single space")
    ]

class TypeOfTypeReader(TaxDumpReader):
    table_name = "typeoftype"
    fields = [
        ("type_name", str, "name of type material type"),
        ("synonyms", str, "alternative names for type material type"),
        ("nomenclature", str, """Taxonomic Code of Nomenclature coded by a single letter:
                                 -- B - International Code for algae, fungi and plants (ICN), previously Botanical Code,
                                 -- P - International Code of Nomenclature of Prokaryotes (ICNP),
                                 -- Z - International Code of Zoological Nomenclature (ICZN),
                                 -- V - International Committee on Taxonomy of Viruses (ICTV) virus classification."""),
        ("description", str, "descriptive text")
    ]

class HostReader(TaxDumpReader):
    table_name = "host"
    fields = [
        ("tax_id", str, "node id"),
        ("potential_hosts", str, "theoretical host list separated by comma ','")
    ]

class TypeMaterialReader(TaxDumpReader):
    table_name = "typematerial"
    fields = [
        ("tax_id", int, "node id"),
        ("tax_name", str, "organism name type material is assigned to"),
        ("type", str, "type material type (see typeoftype.dmp)"),
        ("identifier", str, "identifier in type material collection")
    ]


class RankedLineageReader(TaxDumpReader):
    """
    Select ancestor names for well-established taxonomic ranks
    (species, genus, family, order, class, phylum, kingdom, superkingdom)
    """
    table_name = "rankedlineage"
    fields = [
        ("tax_id", int, "node id"),
        ("tax_name", str, "scientific name of the organism"),
        ("species_name", str, "name of a species (coincide with organism name for species-level nodes)"),
        ("genus_name", str, "genus name when available"),
        ("family_name", str, "family name when available"),
        ("order_name", str, "order name when available"),
        ("class_name", str, "class name when available"),
        ("phylum_name", str, "phylum name when available"),
        ("kingdom_name", str, "kingdom name when available"),
        ("superkingdom_name", str, "superkingdom (domain) name when available")
    ]

class FullNameLineageReader(TaxDumpReader):
    table_name = "fullnamelineage"
    fields = [
        ("tax_id", int, "node id"),
        ("tax_name", str, "scientific name of the organism"),
        ("lineage", str, ("sequence of sncestor names separated by semicolon ';' denoting nodes' ancestors starting "
                          "from the most distant one and ending with the immediate one"))
    ]

class TaxIdLineageReader(TaxDumpReader):
    table_name = "taxidlineage"
    fields = [
        ("tax_id", int, "node id"),
        ("lineage", str, ("sequence of node ids separated by space denoting nodes' ancestors starting from the most "
                          "distant one and ending with the immediate one"))
    ]


def field_spec(field):
    type_map = {int: "integer", str: "text"}
    spec = field[0] + " " + ("integer" if field[0] == "rank" else type_map[field[1]])
    if len(field) > 2:
        spec += " " + field[2]
    return spec


def taxa_loader():
    rows_processed = 0
    for row in NodesReader():
        yield (str(row["tax_id"]), (row["parent"], row["rank"], row["division_id"], row["specified_species"]))
        rows_processed += 1
        if rows_processed % 100000 == 0:
            logger.info("Processed %d taxon rows", rows_processed)

def accession2taxid_loader():
    accessions_in_nt = set()
    rows_processed = 0
    with gzip.open("nt_fasta_headers.gz", mode="rt") as nt_fh:
        for fasta_line in nt_fh:
            accession = fasta_line.split()[0].lstrip(">")
            accessions_in_nt.add(accession)
            rows_processed += 1
            if rows_processed % 1000000 == 0:
                logger.info("Loaded %d NT accession IDs", rows_processed)

    rows_processed, rows_loaded = 0, 0
    for a2t_filename in "nucl_gb", "nucl_wgs":
        with gzip.open(f"{a2t_filename}.accession2taxid.gz", mode="rt") as a2t_fh:
            a2t_fh.readline()
            for line in a2t_fh:
                accession, accession_version, tax_id, gi = line.split()
                if accession_version in accessions_in_nt:
                    if accession_version.endswith(".1"):
                        accession_version = accession_version[:-len(".1")]
                    yield (accession_version, (int(tax_id), ))
                    rows_loaded += 1
                rows_processed += 1
                if rows_processed % 1000000 == 0:
                    logger.info("Processed %d accession2taxid rows (%d%% in NT)",
                                rows_processed, int(100*rows_loaded/rows_processed))


def build_trees():
    logging.basicConfig(level=logging.INFO)

    dl_procs = []
    for a2t_dump in "nucl_gb.accession2taxid.gz", "nucl_wgs.accession2taxid.gz", "prot.accession2taxid.gz":
        if not os.path.exists(a2t_dump):
            cmd = f"curl -O https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/accession2taxid/{a2t_dump}"
            dl_procs.append(subprocess.Popen(cmd, shell=True))
    if not os.path.exists("nt_fasta_headers.gz"):
        cmd = "curl https://ftp.ncbi.nlm.nih.gov/blast/db/FASTA/nt.gz | zgrep '>' | gzip > nt_fasta_headers.gz"
        dl_procs.append(subprocess.Popen(cmd, shell=True))
    if not os.path.exists("nodes.dmp"):
        cmd = "curl https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz | tar -xvz"
        subprocess.run(cmd, shell=True)

    # TODO: pack all bit fields into one byte
    marisa_trie.RecordTrie("IBBB", taxa_loader()).save('taxa.marisa')
    marisa_trie.RecordTrie("I", accession2taxid_loader()).save('accession2taxid.marisa')

    names = collections.defaultdict(dict)
    for row in TaxonomyNamesReader():
        if row["tax_id"] in names and row["name_class"] in names[row["tax_id"]]:
            continue
        if row["name_class"] in {"scientific name", "common name", "genbank common name", "blast name"}:
            names[row["tax_id"]][row["name_class"]] = row["name"]
    taxid2name_array = sorted(((tax_id, row["scientific name"]) for tax_id, row in names.items()), key=lambda i: i[1])
    taxid2pos = {}
    names = io.BytesIO()
    for tax_id, scientific_name in taxid2name_array:
        taxid2pos[tax_id] = names.tell()
        names.write(scientific_name.encode())
        names.write(b"\n")
    with open("scientific_names.zstd", "wb") as fh:
        fh.write(zstandard.compress(names.getvalue()))

    marisa_trie.RecordTrie("I", [(str(tid), (pos, )) for tid, pos in taxid2pos.items()]).save("scientific_names.marisa")

    # TODO: write common names
    def common_names_loader(names):
        for tax_id, tax_names in names.items():
            if "blast name" in tax_names:
                yield (str(tax_id), (tax_names["blast name"].encode(), ))
            elif "genbank common name" in tax_names:
                yield (str(tax_id), (tax_names["genbank common name"].encode(), ))
            elif "common name" in tax_names:
                yield (str(tax_id), (tax_names["common name"].encode(), ))

    # TODO: write (tax_id -> refseq accessions) mapping & possibly rank accessions by informativeness
