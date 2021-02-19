import os
import sys
import subprocess
import enum
import json
import logging
import io
import struct
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

import marisa_trie
import zstandard
import urllib3

from . import Rank, Taxon, Accession, BLASTDatabase

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


class WikipediaDescriptionClient:
    def get_taxonbar_page_ids(self):
        params = dict(action="query", list="embeddedin", eititle="Template:Taxonbar", format="json", eilimit=500)
        while True:
            res = http.request("GET", url="https://en.wikipedia.org/w/api.php", fields=params)
            assert res.status == 200
            page = json.loads(res.data)
            for pageset_start in range(0, len(page["query"]["embeddedin"]), 50):
                yield [str(record["pageid"]) for record in page["query"]["embeddedin"][pageset_start:pageset_start+50]]
            if not page.get("continue"):
                break
            params.update(page["continue"])

    def get_wiki_pages(self, domain="www.wikidata.org", **kwargs):
        params = dict(action="query", prop="revisions", rvprop="content", format="json", **kwargs)
        res = http.request("GET", url=f"https://{domain}/w/api.php", fields=params)
        assert res.status == 200, res
        res_doc = json.loads(res.data)
        for page in res_doc["query"]["pages"].values():
            assert page["ns"] == 0
            assert len(page["revisions"]) == 1
            yield page["pageid"], page["title"], page["revisions"][0]["*"]

    def get_wikidata_linkshere(self, title, max_pages=sys.maxsize):
        params = dict(action="query", prop="linkshere", lhnamespace="0", lhprop="pageid|title", lhlimit=500,
                      format="json", titles=title)
        n_pages = 0
        while True:
            res = http.request("GET", url="https://www.wikidata.org/w/api.php", fields=params)
            assert res.status == 200, res
            res_doc = json.loads(res.data)
            for page_links in res_doc["query"]["pages"].values():
                for pageset_start in range(0, len(page_links["linkshere"]), 50):
                    yield [str(record["pageid"]) for record in page_links["linkshere"][pageset_start:pageset_start+50]]
            n_pages += 1
            if n_pages >= max_pages or not res_doc.get("continue"):
                break
            params.update(res_doc["continue"])

    def get_extracts(self, titles, domain="en.wikipedia.org", extract_chars=1000):
        assert len(titles) <= 20
        params = dict(action="query", prop="extracts", exintro=True, exchars=extract_chars, format="json",
                      titles="|".join(titles))
        res = http.request("GET", url=f"https://{domain}/w/api.php", fields=params)
        assert res.status == 200, res
        res_doc = json.loads(res.data)
        for page in res_doc["query"]["pages"].values():
            if page["ns"] == 0 and "extract" in page and "title" in page:
                yield page
            else:
                logger.error("Error retrieving extract: %s", page)

    def process_pageid_set(self, pageid_set):
        tax_data_by_title = {}
        for pageid, title, page in self.get_wiki_pages(pageids="|".join(pageid_set)):
            page = json.loads(page)
            if "redirect" in page or "enwiki" not in page.get("sitelinks", {}):
                continue
            en_wiki_title = page["sitelinks"]["enwiki"]["title"]
            claims = page["claims"]
            # P31, instance of; P685, NCBI taxid
            if "P31" not in claims or "P685" not in claims:
                continue
            if claims["P31"][0]["mainsnak"]["datavalue"]["value"]["id"] != "Q16521":
                continue
            if claims["P685"][0]["mainsnak"]["snaktype"] == "novalue":
                continue
            taxid = claims["P685"][0]["mainsnak"]["datavalue"]["value"]
            tax_data_by_title[en_wiki_title] = dict(taxid=taxid, wikidata_id=title, en_wiki_title=en_wiki_title)

        titles = list(tax_data_by_title.keys())
        for titleset_start in range(0, len(titles), 20):
            for extract in self.get_extracts(titles[titleset_start:titleset_start+20]):
                tax_data_by_title[extract["title"]]["extract"] = extract["extract"]
        logger.debug("Processed %d pages", len(tax_data_by_title))
        return tax_data_by_title

    def build_index(self, destdir, max_records=sys.maxsize, **threadpool_kwargs):
        index_filename = os.path.join(destdir, "wikipedia_extracts.json")
        with open(index_filename, "w") as fh, ThreadPoolExecutor(**threadpool_kwargs) as executor:
            n_records = 0
            # Q16521, taxon
            for tax_data_set in executor.map(self.process_pageid_set,
                                             self.get_wikidata_linkshere("Q16521", max_pages=max_records)):
                for tax_datum in tax_data_set.values():
                    fh.write(json.dumps(tax_datum) + "\n")
                    n_records += 1
                logger.debug("Wrote %d records", n_records)
                if n_records >= max_records:
                    break
        return index_filename


def read_blastdb_str(fh):
    str_len = struct.unpack(">i", fh.read(4))[0]
    str_contents = fh.read(str_len).decode()
    return str_contents


def field_spec(field):
    type_map = {int: "integer", str: "text"}
    spec = field[0] + " " + ("integer" if field[0] == "rank" else type_map[field[1]])
    if len(field) > 2:
        spec += " " + field[2]
    return spec


def load_taxa():
    rows_processed = 0
    for row in NodesReader():
        yield (str(row["tax_id"]), (row["parent"], row["rank"], row["division_id"], row["specified_species"]))
        rows_processed += 1
        if rows_processed % 100000 == 0:
            logger.info("Processed %d taxon rows", rows_processed)


def load_common_names(names):
    for tax_id, tax_names in names.items():
        if "blast name" in tax_names:
            yield (tax_id, tax_names["blast name"])
        elif "genbank common name" in tax_names:
            yield (tax_id, tax_names["genbank common name"])
        elif "common name" in tax_names:
            yield (tax_id, tax_names["common name"])
        else:
            pass  # FIXME: fall back to en_wiki_title


def preprocess_accession_data(blast_db_names, taxid2refseq):
    all_accessions, duplicate_accessions = set(), set()
    processed_accessions = 0
    for blast_db_name in blast_db_names:
        for accession_id, accession_info in load_accession_info_from_blast_db(blast_db_name):
            accession_info["packed_id"] = Accession._pack_id(Accession, accession_id)
            if accession_id in all_accessions:
                duplicate_accessions.add(accession_id)
                continue
            if blast_db_name.startswith("ref_"):
                taxid2refseq[accession_info["tax_id"]].append(accession_id)
            yield accession_info

            processed_accessions += 1
            all_accessions.add(accession_id)
        logger.info("Processed %s, loaded %d total accessions", blast_db_name, processed_accessions)
    logger.info("%d duplicate accessions skipped", len(duplicate_accessions))


def write_taxid_to_string_index(mapping, index_name, destdir):
    logger.info("Writing string index %s to %s...", index_name, destdir)
    taxid2pos = {}
    string_db = io.BytesIO()
    for tax_id, string_value in mapping:
        taxid2pos[tax_id] = string_db.tell()
        string_db.write(string_value.replace("\n", " ").encode())
        string_db.write(b"\n")
    with open(os.path.join(destdir, f"{index_name}.zstd"), "wb") as fh:
        fh.write(zstandard.compress(string_db.getvalue()))

    t = marisa_trie.RecordTrie("I", [(str(tid), (pos, )) for tid, pos in taxid2pos.items()])
    t.save(os.path.join(destdir, f"{index_name}.marisa"))
    logger.info("Completed writing string index %s to %s", index_name, destdir)


def fetch_file(url):
    local_filename = "/mnt/downloads/" + os.path.basename(url)
    if not os.path.exists(local_filename):
        with open(local_filename, "w") as fh:
            fh.write(http.request("GET", url).data.decode())
    return local_filename


def load_wikidata(field="wikidata_id"):
    # TODO: gzip, cache dir
    with open("/mnt/wikipedia_extracts.json") as fh:
        for line in fh:
            record = json.loads(line)
            if field in record:
                yield (record["taxid"], (int(record[field].lstrip("Q")), ) if field == "wikidata_id" else record[field])


def build_trees(blast_databases=os.environ.get("BLAST_DATABASES", "").split(), destdir=os.path.dirname(__file__)):
    logging.basicConfig(level=logging.INFO)

    if not blast_databases:
        blast_databases = [db.name for db in BLASTDatabase]

    if not os.path.exists("nodes.dmp"):
        cmd = "curl https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz | tar -xvz"
        subprocess.run(cmd, shell=True)

    marisa_trie.RecordTrie("I", load_wikidata()).save(os.path.join(destdir, 'wikidata.marisa'))
    write_taxid_to_string_index(mapping=load_wikidata(field="extract"), index_name="descriptions", destdir=destdir)
    write_taxid_to_string_index(mapping=load_wikidata(field="en_wiki_title"), index_name="en_wiki_titles",
                                destdir=destdir)
    # TODO: pack all bit fields into one byte
    marisa_trie.RecordTrie("IBBB", load_taxa()).save(os.path.join(destdir, 'taxa.marisa'))

    taxid2refseq = defaultdict(list)

    accession_cache = os.path.join(os.environ["BLASTDB"], "accession_cache")
    with open(accession_cache, "w") as fh:
        for acc_info in preprocess_accession_data(blast_databases, taxid2refseq=taxid2refseq):
            print(json.dumps(acc_info), file=fh)

    def load_accession_data(xform):
        with open(accession_cache) as fh:
            for line in fh:
                yield xform(json.loads(line))

    def acc_xform(acc_info):
        return (
            acc_info["packed_id"],
            (acc_info["tax_id"], ((BLASTDatabase[acc_info["db_name"]].value << 8) + acc_info["volume_id"]))
        )

    def db_path(db_package):
        return os.path.join(destdir, "..", "db_packages", db_package, db_package, "db.marisa")
    t = marisa_trie.RecordTrie("IH", load_accession_data(acc_xform))
    t.save(db_path("taxoniq_accessions"))
    logger.info("Completed writing taxoniq_accessions db")
    t = marisa_trie.RecordTrie("I", load_accession_data(lambda d: (d["packed_id"], (d["offset"], ))))
    t.save(db_path("taxoniq_accession_offsets"))
    logger.info("Completed writing taxoniq_accession_offsets db")
    t = marisa_trie.RecordTrie("I", load_accession_data(lambda d: (d["packed_id"], (d["length"], ))))
    t.save(db_path("taxoniq_accession_lengths"))
    logger.info("Completed writing taxoniq_accession_lengths db")
    write_taxid_to_string_index(mapping=[(tid, ",".join(acc)) for tid, acc in taxid2refseq.items()],
                                index_name="taxid2refseqs", destdir=destdir)

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
    write_taxid_to_string_index(mapping=load_common_names(names), index_name="common_names", destdir=destdir)


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
    for assembly_molecules in ThreadPoolExecutor().map(process_assembly_report, assembly_summaries):
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
        taxid2gbaccn[assembly_molecule["taxid"]] = ",".join(sorted(accessions_for_taxon))
    print("taxa with refseq:", len(taxa_with_refseq), sum(taxa_with_refseq.values()))
    print("gb accessions found in nt:", len(gb), sum(gb.values()))
    print("gb accessions not found in nt:", len(mismatch), sum(mismatch.values()))
    write_taxid_to_string_index(mapping=taxid2gbaccn.items(), index_name="taxid2refseq", destdir=destdir)


def load_accession_info_from_blast_db(db_name):
    accessions, db_volumes = {}, []
    for line in subprocess.check_output(['blastdbcmd', '-list', os.environ["BLASTDB"]]).decode().splitlines():
        db_path, db_type = line.strip().split()
        assert db_path.startswith(os.environ["BLASTDB"])
        db_path = db_path[len(os.environ["BLASTDB"]):].lstrip("/")
        if db_path == db_name or db_path.startswith(db_name + "."):
            db_volumes.append(os.path.join(os.environ["BLASTDB"], db_path))
            # Create a placeholder sparse file for nsq (sequence data) so blastdbcmd won't complain about it missing
            subprocess.run(
                ["dd", "if=/dev/zero", f"of={db_volumes[-1]}.nsq", "bs=1", "count=0", "seek=8G", "status=none"]
            )

    for db_volume in db_volumes:
        logger.info("Processing BLAST db volume %s", db_volume)
        if not os.path.exists(f"{db_volume}.nin"):
            continue
        accessions_for_volume = {}
        blastdbcmd = ['blastdbcmd', '-db', os.path.basename(db_volume), '-entry', 'all', '-outfmt', '%a %o %l %T']
        for line in subprocess.check_output(blastdbcmd).decode().splitlines():
            accession_id, ordinal_id, length, tax_id = line.strip().split()
            assert accession_id not in accessions_for_volume
            accessions_for_volume[accession_id] = dict(ordinal_id=int(ordinal_id),
                                                       length=int(length),
                                                       tax_id=int(tax_id))

        with open(f"{db_volume}.nin", "rb") as fh:
            # See ncbi-blast-2.9.0+-src/c++/src/objtools/blast/seqdb_reader/seqdbfile.cpp
            format_version, sequence_type, volume = struct.unpack(">III", fh.read(12))
            assert format_version == 5
            title, lmdb_file, create_date = read_blastdb_str(fh), read_blastdb_str(fh), read_blastdb_str(fh)  # noqa
            num_oids = struct.unpack(">I", fh.read(4))[0]
            volume_length = struct.unpack("<q", fh.read(8))[0]  # noqa: F841
            max_seq_length = struct.unpack(">I", fh.read(4))[0]  # noqa: F841
            header_array = struct.unpack(f">{num_oids + 1}I", fh.read(4 * (num_oids + 1)))  # noqa: F841
            sequence_array = struct.unpack(f">{num_oids + 1}I", fh.read(4 * (num_oids + 1)))
            db_type = "Nucleotide" if sequence_type == 0 else "Protein"
            logger.info("%s database %s %s (%d records)", db_type, title, create_date, num_oids)
            for accession_id, accession_info in accessions_for_volume.items():
                assert accession_id not in accessions
                try:
                    volume_id = int(os.path.basename(db_volume).rsplit(".", 1)[1])
                except IndexError:
                    volume_id = 0
                accession_info["db_name"] = db_name
                accession_info["volume_id"] = volume_id
                accession_info["offset"] = sequence_array[accession_info["ordinal_id"]]
                yield (accession_id, accession_info)

# TODO: load WoL tree distance information
# TODO: rank accessions by informativeness
# TODO: load virus host and refseq data (Viruses_RefSeq_and_neighbors_genome_data.tab)
# TODO: use blastdb-manifest.json
