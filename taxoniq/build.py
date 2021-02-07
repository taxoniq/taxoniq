import os
import subprocess
import enum
import gzip
import logging
import io
import concurrent.futures
from collections import defaultdict

import marisa_trie
import zstandard
import urllib3

from . import Rank, Taxon

logger = logging.getLogger(__name__)

http = urllib3.PoolManager()


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


def common_names_loader(names):
    for tax_id, tax_names in names.items():
        if "blast name" in tax_names:
            yield (tax_id, tax_names["blast name"])
        elif "genbank common name" in tax_names:
            yield (tax_id, tax_names["genbank common name"])
        elif "common name" in tax_names:
            yield (tax_id, tax_names["common name"])


def write_taxid_to_string_index(mapping, index_name, destdir):
    taxid2pos = {}
    string_db = io.BytesIO()
    for tax_id, string_value in mapping:
        taxid2pos[tax_id] = string_db.tell()
        string_db.write(string_value.encode())
        string_db.write(b"\n")
    with open(os.path.join(destdir, f"{index_name}.zstd"), "wb") as fh:
        fh.write(zstandard.compress(string_db.getvalue()))

    t = marisa_trie.RecordTrie("I", [(str(tid), (pos, )) for tid, pos in taxid2pos.items()])
    t.save(os.path.join(destdir, f"{index_name}.marisa"))


def fetch_file(url):
    local_filename = "/mnt/downloads/" + os.path.basename(url)
    if not os.path.exists(local_filename):
        with open(local_filename, "w") as fh:
            fh.write(http.request("GET", url).data.decode())
    return local_filename


def build_trees(destdir=os.path.dirname(__file__)):
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
    marisa_trie.RecordTrie("IBBB", taxa_loader()).save(os.path.join(destdir, 'taxa.marisa'))
    for proc in dl_procs:
        if proc.wait() != os.EX_OK:
            raise Exception(f"{proc} failed")
    marisa_trie.RecordTrie("I", accession2taxid_loader()).save(os.path.join(destdir, 'accession2taxid.marisa'))

    names, sn2taxid = defaultdict(dict), {}
    for row in TaxonomyNamesReader():
        if row["tax_id"] in names and row["name_class"] in names[row["tax_id"]]:
            continue
        if row["name_class"] in {"scientific name", "common name", "genbank common name", "blast name"}:
            names[row["tax_id"]][row["name_class"]] = row["name"]
        if row["name_class"] == "scientific name":
            sn2taxid[row["name"]] = int(row["tax_id"])
    taxid2name_array = sorted(((tax_id, row["scientific name"]) for tax_id, row in names.items()), key=lambda i: i[1])
    write_taxid_to_string_index(mapping=taxid2name_array, index_name="scientific_names", destdir=destdir)
    t = marisa_trie.RecordTrie("I", [(sn, (tid, )) for sn, tid in sn2taxid.items()])
    t.save(os.path.join(destdir, "sn2taxid.marisa"))
    write_taxid_to_string_index(mapping=common_names_loader(names), index_name="common_names", destdir=destdir)


def process_assembly_report(assembly_summary):
    ftp_path = assembly_summary["ftp_path"]
    assembly_report_url = f"{ftp_path.replace('ftp', 'https', 1)}/{os.path.basename(ftp_path)}_assembly_report.txt"
    assembly_report_fields = ("sequence_name", "sequence_role", "assigned_molecule", "assigned_molecule_location_type",
                              "genbank_accn", "relationship", "refseq_accn", "assembly_unit", "sequence_length",
                              "ucsc_style_name")

    molecules = []
    with open(fetch_file(assembly_report_url)) as assembly_report:
        for line in assembly_report:
            if line.startswith("#"):
                continue
            molecule_summary = dict(zip(assembly_report_fields, line.strip().split("\t")))
            if molecule_summary["sequence_role"] != "assembled-molecule":
                continue
            molecule_summary.update(assembly_summary)
            molecules.append(molecule_summary)
    return molecules


def download_refseq_accessions(destdir=os.path.dirname(__file__)):
    # See https://www.ncbi.nlm.nih.gov/genome/doc/ftpfaq/#files
    # FIXME: neither genbank nor refseq id represented in nt
    # in assemblies: 6239 6239 Caenorhabditis elegans reference genome
    # ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/002/985/GCF_000002985.6_WBcel235
    #         II Chromosome BX284602.5 NC_003280.10 15279421
    # in nt: >AC182480.1 Caenorhabditis elegans chromosome II, complete sequence
    assembly_summary_url = "https://ftp.ncbi.nlm.nih.gov/genomes/refseq/assembly_summary_refseq.txt"
    assembly_summary_fields = ("assembly_accession", "bioproject", "biosample", "wgs_master", "refseq_category",
                               "taxid", "species_taxid", "organism_name", "infraspecific_name", "isolate",
                               "version_status", "assembly_level", "release_type", "genome_rep", "seq_rel_date",
                               "asm_name", "submitter", "gbrs_paired_asm", "paired_asm_comp", "ftp_path",
                               "excluded_from_refseq", "relation_to_type_material")
    a2t = Taxon._get_db(Taxon, "a2t")
    taxa_with_refseq = defaultdict(int)
    gb, mismatch = defaultdict(int), defaultdict(int)
    assembly_summaries = []
    with open(fetch_file(assembly_summary_url)) as assembly_summary_fh:
        for line in assembly_summary_fh:
            if line.startswith("#"):
                continue
            assembly_summary = dict(zip(assembly_summary_fields, line.strip().split("\t")))
            if assembly_summary["release_type"] != "Major":
                continue
            assembly_summaries.append(assembly_summary)
    taxid2gbaccn = {}
    duplicate_assy_taxids = defaultdict(set)
    for assembly_molecules in concurrent.futures.ThreadPoolExecutor().map(process_assembly_report, assembly_summaries):
        accessions_for_taxon = []
        for assembly_molecule in assembly_molecules:
            if assembly_molecule["taxid"] in taxid2gbaccn:
                # TODO: discard non-representative assemblies for taxa that have representative/reference ones
                # TODO: investigate mismatch and duplicate assemblies
                print(f"WARNING: multiple refseq assemblies found for {assembly_molecule}")
                duplicate_assy_taxids[assembly_molecule["taxid"]].add(taxid2gbaccn[assembly_molecule["taxid"]])
                duplicate_assy_taxids[assembly_molecule["taxid"]].add(assembly_molecule["genbank_accn"])
            taxa_with_refseq[assembly_molecule["taxid"]] += 1
            genbank_accn = assembly_molecule["genbank_accn"]
            if genbank_accn.endswith(".1"):
                genbank_accn = genbank_accn[:-len(".1")]
            if genbank_accn in a2t:
                gb[genbank_accn] += 1
                accessions_for_taxon.append(genbank_accn)
            else:
                mismatch[genbank_accn] += 1
        taxid2gbaccn[assembly_molecule["taxid"]] = ",".join(accessions_for_taxon)
    print("taxa with refseq:", len(taxa_with_refseq), sum(taxa_with_refseq.values()))
    print("gb accessions found in nt:", len(gb), sum(gb.values()))
    print("gb accessions not found in nt:", len(mismatch), sum(mismatch.values()))
    write_taxid_to_string_index(mapping=taxid2gbaccn.items(), index_name="taxid2refseq", destdir=destdir)

# TODO: load WoL tree distance information
# TODO: rank accessions by informativeness
# TODO: load virus host and refseq data (Viruses_RefSeq_and_neighbors_genome_data.tab)
