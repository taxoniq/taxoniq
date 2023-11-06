import io
import json
import logging
import os
import re
import struct
import subprocess
import sys
import warnings
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256

import urllib3
import zstandard

from . import Accession, BLASTDatabase, RecordTrie
from .tax_dump_readers import HostReader, NodesReader, TaxonomyNamesReader

logger = logging.getLogger(__name__)

http = urllib3.PoolManager(maxsize=min(64, os.cpu_count() + 8))

db_packages_dir = os.path.join(os.path.dirname(__file__), "..", "db_packages")


class WikipediaDescriptionClient:
    def get_taxonbar_page_ids(self):
        params = dict(
            action="query",
            list="embeddedin",
            eititle="Template:Taxonbar",
            format="json",
            eilimit=500,
        )
        while True:
            res = http.request("GET", url="https://en.wikipedia.org/w/api.php", fields=params)
            assert res.status == 200
            page = json.loads(res.data)
            for pageset_start in range(0, len(page["query"]["embeddedin"]), 50):
                yield [
                    str(record["pageid"]) for record in page["query"]["embeddedin"][pageset_start : pageset_start + 50]
                ]
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
        params = dict(
            action="query",
            prop="linkshere",
            lhnamespace="0",
            lhprop="pageid|title",
            lhlimit=500,
            format="json",
            titles=title,
        )
        n_pages = 0
        while True:
            res = http.request("GET", url="https://www.wikidata.org/w/api.php", fields=params)
            assert res.status == 200, res
            res_doc = json.loads(res.data)
            for page_links in res_doc["query"]["pages"].values():
                for pageset_start in range(0, len(page_links["linkshere"]), 50):
                    yield [
                        str(record["pageid"]) for record in page_links["linkshere"][pageset_start : pageset_start + 50]
                    ]
            n_pages += 1
            if n_pages >= max_pages or not res_doc.get("continue"):
                break
            params.update(res_doc["continue"])

    def get_extracts(self, titles, domain="en.wikipedia.org", extract_chars=9000):
        assert len(titles) <= 20
        params = dict(
            action="query",
            prop="extracts",
            exintro=True,
            exchars=extract_chars,
            format="json",
            titles="|".join(titles),
        )
        res = http.request("GET", url=f"https://{domain}/w/api.php", fields=params)
        assert res.status == 200, res
        res_doc = json.loads(res.data)
        for page in res_doc["query"]["pages"].values():
            if page["ns"] == 0 and "extract" in page and "title" in page:
                page["extract"] = re.sub(
                    r'<p class="mw-empty-elt">.+?</p>',
                    "",
                    page["extract"],
                    flags=re.DOTALL,
                )
                page["extract"] = re.sub(r"\s*<!--.+", "", page["extract"], flags=re.DOTALL)
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
            for extract in self.get_extracts(titles[titleset_start : titleset_start + 20]):
                tax_data_by_title[extract["title"]]["extract"] = extract["extract"]
        logger.debug("Processed %d pages", len(tax_data_by_title))
        return tax_data_by_title

    def build_index(self, destdir, max_records=sys.maxsize, **threadpool_kwargs):
        index_filename = os.path.join(destdir, "wikipedia_extracts.json")
        with open(index_filename, "w") as fh, ThreadPoolExecutor(**threadpool_kwargs) as executor:
            n_records = 0
            # Q16521, taxon
            for tax_data_set in executor.map(
                self.process_pageid_set,
                self.get_wikidata_linkshere("Q16521", max_pages=max_records),
            ):
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
        yield (
            str(row["tax_id"]),
            (row["parent"], row["rank"], row["division_id"], row["specified_species"]),
        )
        rows_processed += 1
        if rows_processed % 100000 == 0:
            logger.info("Processed %d taxon rows", rows_processed)


def load_child_nodes():
    taxid2childnodes = defaultdict(list)
    for tax_id, tax_data in load_taxa():
        if tax_id != "1":
            taxid2childnodes[tax_data[0]].append(tax_id)
    for tax_id, child_nodes in taxid2childnodes.items():
        yield tax_id, ",".join(child_nodes)


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


def preprocess_accession_data(blast_db_names, taxid2refrep):
    all_accessions, duplicate_accessions = set(), set()
    processed_accessions = 0
    for blast_db_name in blast_db_names:
        for accession_id, accession_info in load_accession_info_from_blast_db(blast_db_name):
            accession_info["packed_id"] = Accession._pack_id(Accession, accession_id)
            if accession_id in all_accessions:
                duplicate_accessions.add(accession_id)
                continue
            if blast_db_name.startswith("ref_") and "rep_genomes" in blast_db_name:
                taxid2refrep[accession_info["tax_id"]].append(accession_id)
            yield accession_info

            processed_accessions += 1
            all_accessions.add(accession_id)
        logger.info(
            "Processed %s, loaded %d total accessions",
            blast_db_name,
            processed_accessions,
        )
    logger.info("%d duplicate accessions skipped", len(duplicate_accessions))


def write_taxid_to_string_index(mapping, index_name, destdir):
    logger.info("Writing string index %s to %s...", index_name, destdir)
    taxid2pos, str2pos = {}, {}
    string_db = io.BytesIO()
    for tax_id, string_value in mapping:
        string_value_csum = sha256(string_value.encode()).digest()
        if string_value_csum in str2pos:
            taxid2pos[tax_id] = str2pos[string_value_csum]
        else:
            taxid2pos[tax_id] = string_db.tell()
            string_db.write(string_value.replace("\n", " ").encode())
            string_db.write(b"\n")
            str2pos[string_value_csum] = taxid2pos[tax_id]
    with open(os.path.join(destdir, f"{index_name}.zstd"), "wb") as fh:
        fh.write(zstandard.compress(string_db.getvalue()))

    t = RecordTrie("I", [(str(tid), (pos,)) for tid, pos in taxid2pos.items()])
    t.save(os.path.join(destdir, f"{index_name}.marisa"))
    logger.info("Completed writing string index %s to %s", index_name, destdir)


def fetch_file(url):
    download_cache = os.path.join(os.environ["BLASTDB"], "downloads")
    os.makedirs(download_cache, exist_ok=True)
    local_filename = os.path.join(download_cache, os.path.basename(url))
    if not os.path.exists(local_filename):
        with open(local_filename, "w") as fh:
            res = http.request("GET", url)
            assert res.status == 200
            fh.write(res.data.decode())
    return local_filename


def load_wikidata(field="wikidata_id"):
    with open("wikipedia_extracts.json") as fh:
        for line in fh:
            record = json.loads(line)
            if field in record:
                yield (
                    record["taxid"],
                    (int(record[field].lstrip("Q")),) if field == "wikidata_id" else record[field],
                )


def load_hosts():
    for row in HostReader():
        yield row["tax_id"], row["potential_hosts"]


def get_virus_genome_data():
    virus_genome_data = []
    virus_data_url = "https://ftp.ncbi.nlm.nih.gov/genomes/Viruses/Viruses_RefSeq_and_neighbors_genome_data.tab"
    virus_data_fields = (
        "representative",
        "neighbor",
        "host",
        "selected_lineage",
        "taxonomy_name",
        "segment_name",
    )
    with open(fetch_file(virus_data_url)) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            virus_genome_data.append(dict(zip(virus_data_fields, line.strip().split("\t"))))
    return virus_genome_data


def build_trees(blast_databases=os.environ.get("BLAST_DATABASES", "").split(), destdir=None):
    logging.basicConfig(level=logging.INFO)

    if destdir is None:
        destdir = os.path.join(db_packages_dir, "ncbi_taxon_db", "ncbi_taxon_db")

    if not blast_databases:
        blast_databases = [db.name for db in BLASTDatabase]

    RecordTrie("I", load_wikidata()).save(os.path.join(destdir, "wikidata.marisa"))
    write_taxid_to_string_index(
        mapping=load_wikidata(field="extract"),
        index_name="description",
        destdir=destdir,
    )
    write_taxid_to_string_index(
        mapping=load_wikidata(field="en_wiki_title"),
        index_name="en_wiki_title",
        destdir=destdir,
    )
    # TODO: pack all bit fields into one byte
    RecordTrie("IBBB", load_taxa()).save(os.path.join(destdir, "taxa.marisa"))
    write_taxid_to_string_index(mapping=load_child_nodes(), index_name="child_nodes", destdir=destdir)
    write_taxid_to_string_index(mapping=load_hosts(), index_name="host", destdir=destdir)

    taxid2refrep = defaultdict(list)

    accession_cache = os.path.join(os.environ["BLASTDB"], "accession_cache")
    with open(accession_cache, "w") as fh:
        for acc_info in preprocess_accession_data(blast_databases, taxid2refrep=taxid2refrep):
            print(json.dumps(acc_info), file=fh)

    def load_accession_data(xform):
        with open(accession_cache) as fh:
            for line in fh:
                yield xform(json.loads(line))

    def acc_xform(acc_info):
        return (
            acc_info["packed_id"],
            (
                acc_info["tax_id"],
                ((BLASTDatabase[acc_info["db_name"]].value << 8) + acc_info["volume_id"]),
            ),
        )

    def db_path(db_name, filename="db.marisa"):
        ncbi_db_name = "genbank" if "nt" in blast_databases else "refseq"
        db_package = f"ncbi_{ncbi_db_name}_{db_name}"
        return os.path.join(db_packages_dir, db_package, db_package, filename)

    def write_index_version(db_name):
        with open("latest-dir") as ts, open(db_path(db_name, filename="version.py"), "w") as fh:
            fh.write(f"db_timestamp = '{ts.read().strip()}'")

    t = RecordTrie("IH", load_accession_data(acc_xform))
    t.save(db_path("accession_db"))
    write_index_version("accession_db")
    logger.info("Completed writing %s", db_path("accession_db"))
    t = RecordTrie("I", load_accession_data(lambda d: (d["packed_id"], (d["offset"],))))
    t.save(db_path("accession_offsets"))
    write_index_version("accession_offsets")
    logger.info("Completed writing %s", db_path("accession_offsets"))
    t = RecordTrie("I", load_accession_data(lambda d: (d["packed_id"], (d["length"],))))
    t.save(db_path("accession_lengths"))
    write_index_version("accession_lengths")
    logger.info("Completed writing %s", db_path("accession_lengths"))
    write_taxid_to_string_index(
        mapping=[(tid, ",".join(acc)) for tid, acc in taxid2refrep.items()],
        index_name="taxid2refrep",
        destdir=destdir,
    )

    # FIXME: if we include non-rep refseq accessions, we should index those accessions' positions in nt
    taxid2refseq = index_refseq_accessions(destdir=destdir)
    write_taxid_to_string_index(mapping=taxid2refseq.items(), index_name="taxid2refseq", destdir=destdir)

    names, sn2taxid = defaultdict(dict), {}
    for row in TaxonomyNamesReader():
        if row["tax_id"] in names and row["name_class"] in names[row["tax_id"]]:
            continue
        if row["name_class"] in {
            "scientific name",
            "common name",
            "genbank common name",
            "blast name",
        }:
            names[row["tax_id"]][row["name_class"]] = row["name"]
        if row["name_class"] == "scientific name":
            sn2taxid[row["name"]] = int(row["tax_id"])
    taxid2name_array = sorted(
        ((tax_id, row["scientific name"]) for tax_id, row in names.items()),
        key=lambda i: i[1],
    )
    write_taxid_to_string_index(mapping=taxid2name_array, index_name="scientific_name", destdir=destdir)
    t = RecordTrie("I", [(sn, (tid,)) for sn, tid in sn2taxid.items()])
    t.save(os.path.join(destdir, "sn2taxid.marisa"))
    write_taxid_to_string_index(mapping=load_common_names(names), index_name="common_name", destdir=destdir)
    with open(os.path.join(destdir, "version.py"), "w") as fh:
        fh.write(f"db_timestamp = {int(os.stat('nodes.dmp').st_mtime)}")


def process_assembly_report(assembly_summary):
    ftp_path = assembly_summary["ftp_path"]
    assembly_report_url = f"{ftp_path}/{os.path.basename(ftp_path)}_assembly_report.txt"
    assembly_report_fields = (
        "sequence_name",
        "sequence_role",
        "assigned_molecule",
        "assigned_molecule_location_type",
        "genbank_accn",
        "relationship",
        "refseq_accn",
        "assembly_unit",
        "sequence_length",
        "ucsc_style_name",
    )
    molecules = []
    if ftp_path.startswith("https://ftp.ncbi.nlm.nih.gov"):
        with open(fetch_file(assembly_report_url)) as assembly_report:
            for line in assembly_report:
                if line.startswith("#"):
                    continue
                molecule_summary = dict(zip(assembly_report_fields, line.strip().split("\t")))
                if molecule_summary["sequence_role"] != "assembled-molecule":
                    continue
                molecule_summary.update(assembly_summary)
                molecules.append(molecule_summary)
    else:
        warnings.warn(f"Invalid assembly summary: {assembly_summary}")
    return molecules


def index_refseq_accessions(destdir):
    # See https://www.ncbi.nlm.nih.gov/genome/doc/ftpfaq/#files
    # FIXME: neither genbank nor refseq id represented in nt
    # in assemblies: 6239 6239 Caenorhabditis elegans reference genome
    # ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/002/985/GCF_000002985.6_WBcel235
    #         II Chromosome BX284602.5 NC_003280.10 15279421
    # in nt: >AC182480.1 Caenorhabditis elegans chromosome II, complete sequence
    assembly_summary_url = "https://ftp.ncbi.nlm.nih.gov/genomes/refseq/assembly_summary_refseq.txt"
    assembly_summary_fields = (
        "assembly_accession",
        "bioproject",
        "biosample",
        "wgs_master",
        "refseq_category",
        "taxid",
        "species_taxid",
        "organism_name",
        "infraspecific_name",
        "isolate",
        "version_status",
        "assembly_level",
        "release_type",
        "genome_rep",
        "seq_rel_date",
        "asm_name",
        "submitter",
        "gbrs_paired_asm",
        "paired_asm_comp",
        "ftp_path",
        "excluded_from_refseq",
        "relation_to_type_material",
    )
    assembly_summaries = []
    with open(fetch_file(assembly_summary_url)) as assembly_summary_fh:
        for line in assembly_summary_fh:
            if line.startswith("#"):
                continue
            assembly_summary = dict(zip(assembly_summary_fields, line.strip().split("\t")))
            if assembly_summary["release_type"] != "Major":
                continue
            if "FETCH_REFSEQ_ASSEMBLIES" in os.environ:
                if assembly_summary["organism_name"] not in os.environ["FETCH_REFSEQ_ASSEMBLIES"].split(","):
                    continue
            assembly_summaries.append(assembly_summary)
    taxid2assemblies, taxid2accessions = defaultdict(list), {}
    for assembly_molecules in ThreadPoolExecutor().map(process_assembly_report, assembly_summaries):
        if len(assembly_molecules) == 0:
            continue  # draft assembly
        taxid2assemblies[assembly_molecules[0]["taxid"]].append(assembly_molecules)
        if assembly_molecules[0]["species_taxid"] != assembly_molecules[0]["taxid"]:
            taxid2assemblies[assembly_molecules[0]["species_taxid"]].append(assembly_molecules)
    for taxid, assemblies in taxid2assemblies.items():
        best_assembly = sorted(assemblies, key=assembly_sort_key)[-1]
        taxid2accessions[taxid] = ",".join(sorted([m["genbank_accn"] for m in best_assembly]))
    return taxid2accessions


def load_accession_info_from_blast_db(db_name):
    """
    ncbi-blast-2.9.0+/c++/src/objtools/blast/seqdb_reader/sequence_files.txt:

    The nucleotide data is stored in packed NcbiNa2 format.  This format
    uses two bits for each nucleotide base (letter), using the values A=0,
    C=1, G=2, and T=3.  Four such values are stored in each byte.  The
    bases are stored in each byte starting at the most significant bits,
    and proceding down to the least significant.  For example, bases TACG
    are encoded as 3,0,1,2, and then (3 << 6) + (1 << 2) + 2, yielding an
    (unsigned) byte value of 198.

    To find the number of bytes used to store a nucleotide sequence, the
    end point (as a byte offset) is subtracted from the starting point.
    Since nucleotide sequences are packed four bases per byte, this must
    be multiplied by four to get the sequence length in bases.

    But this technique does not tell us the exact length -- to find the
    exact length, we need to know how many of the bases in the last byte
    are part of the sequence.  BlastDB solves this problem by using the
    last base of the last byte to store a number from 0-3; this is the
    "remainder", a count of how many of the bases in the last byte are
    part of the sequence.  If a sequence is exactly divisible by four, an
    additional byte must be appended to contain this count (which will be
    zero.)  For the sequence (TACG), the full byte encoding is (225, 0).

    Another example: The sequence TGGTTACAAC would first be broken into
    byte sized chunks (TGGT,TACA,AC).  Each base is encoded numerically,
    (3223,3010,01).  The last byte only contains 2 bases, so it is padded
    with a zero base and the remainder (2), yielding (3223,3010,0102).  In
    decimal this is 235, 196, and 18, or in hexadecimal, (EB, C4, 12).
    """
    accessions, db_volumes = {}, []
    for line in subprocess.check_output(["blastdbcmd", "-list", os.environ["BLASTDB"]]).decode().splitlines():
        db_path, db_type = line.strip().split()
        assert db_path.startswith(os.environ["BLASTDB"])
        db_path = db_path[len(os.environ["BLASTDB"]) :].lstrip("/")
        if db_path == db_name or db_path.startswith(db_name + "."):
            db_volumes.append(os.path.join(os.environ["BLASTDB"], db_path))

    for db_volume in db_volumes:
        logger.info("Processing BLAST db volume %s", db_volume)
        if not os.path.exists(f"{db_volume}.nin"):
            continue
        accessions_for_volume = {}
        blastdbcmd = [
            "blastdbcmd",
            "-db",
            os.path.basename(db_volume),
            "-entry",
            "all",
            "-outfmt",
            "%a %o %l %T",
        ]
        for line in subprocess.check_output(blastdbcmd).decode().splitlines():
            accession_id, ordinal_id, length, tax_id = line.strip().split()
            assert accession_id not in accessions_for_volume
            accessions_for_volume[accession_id] = dict(
                ordinal_id=int(ordinal_id), length=int(length), tax_id=int(tax_id)
            )

        with open(f"{db_volume}.nin", "rb") as fh:
            # See ncbi-blast-2.9.0+-src/c++/src/objtools/blast/seqdb_reader/seqdbfile.cpp
            format_version, sequence_type, volume = struct.unpack(">III", fh.read(12))
            assert format_version == 5
            title, _, create_date = (
                read_blastdb_str(fh),
                read_blastdb_str(fh),
                read_blastdb_str(fh),
            )
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


assembly_sort_preferences = {
    "refseq_category": ["representative genome", "reference genome"],
    "assembly_level": ["Contig", "Scaffold", "Chromosome", "Complete Genome"],
    "genome_rep": ["Partial", "Full"],
}


def assembly_sort_key(assembly):
    sort_key = []
    for key, values in assembly_sort_preferences.items():
        sort_key.append(values.index(assembly[0][key]) if assembly[0][key] in values else -1)
    sort_key.append(assembly[0]["seq_rel_date"])
    return sort_key


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    if len(sys.argv) != 2:
        exit(f"Usage: {os.path.basename(__file__)} (trees|wikipedia_extracts)")
    if sys.argv[1] == "trees":
        if "BLAST_DATABASES" in os.environ:
            build_trees()
        else:
            build_trees(blast_databases=[db.name for db in BLASTDatabase if db.name not in {"nt", "nr"}])
            build_trees(blast_databases=[db.name for db in BLASTDatabase])
    elif sys.argv[1] == "wikipedia-extracts":
        WikipediaDescriptionClient().build_index(destdir=os.path.join(os.path.dirname(__file__), ".."))
    else:
        raise Exception("Unknown command")

# TODO: load WoL tree distance information
# TODO: load virus host and refseq data (Viruses_RefSeq_and_neighbors_genome_data.tab)
# TODO: use blastdb-manifest.json
