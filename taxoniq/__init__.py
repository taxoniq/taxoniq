import os
from enum import Enum
from typing import List, Union

import ncbi_taxon_db
import urllib3
import zstandard

try:
    import ncbi_genbank_accession_db as accession_db
except ImportError:
    import ncbi_refseq_accession_db as accession_db
try:
    import ncbi_genbank_accession_lengths as accession_lengths
except ImportError:
    import ncbi_refseq_accession_lengths as accession_lengths
try:
    import ncbi_genbank_accession_offsets as accession_offsets
except ImportError:
    import ncbi_refseq_accession_offsets as accession_offsets

from marisa_trie import RecordTrie

from .util import NcbiNa2Decoder
from .version import __version__  # noqa

Rank = Enum(
    "Rank",
    (
        "biotype clade class cohort family forma forma_specialis genotype genus infraclass infraorder isolate kingdom "
        "morph order parvorder pathogroup phylum section series serogroup serotype species species_group species_subgroup "
        "strain subclass subcohort subfamily subgenus subkingdom suborder subphylum subsection subspecies subtribe "
        "subvariety superclass superfamily superkingdom superorder superphylum tribe varietas no_rank"
    ),
)


BLASTDatabase = Enum(
    "BLASTDatabase", ("ref_viruses_rep_genomes ref_prok_rep_genomes ref_euk_rep_genomes Betacoronavirus nt")
)


class TaxoniqException(Exception):
    pass


class NoValue(TaxoniqException):
    pass


class DatabaseService:
    _databases = {}

    def _get_db(self, db_name):
        if db_name not in self._databases:
            db_type, filename = self._db_files[db_name]
            if db_type == zstandard:
                with open(filename, "rb") as fh:
                    self._databases[db_name] = zstandard.decompress(fh.read())
            else:
                self._databases[db_name] = db_type.mmap(filename)
        return self._databases[db_name]


class ItemAttrAccess:
    def __getitem__(self, item):
        return getattr(self, item)


class Accession(DatabaseService, ItemAttrAccess):
    """
    An object representing an NCBI GenBank nucleotide or protein sequence accession ID.
    This is used by Taxoniq to represent sequences associated with taxons; use :class:`Taxon` as the starting point.
    """

    _db_files = {
        "accessions": (RecordTrie("IH"), accession_db.db),
        "accession_offsets": (RecordTrie("I"), accession_offsets.db),
        "accession_lengths": (RecordTrie("I"), accession_lengths.db),
    }
    http = urllib3.PoolManager(maxsize=min(32, os.cpu_count() + 4))
    s3_host = "ncbi-blast-databases.s3.amazonaws.com"

    def __init__(self, accession_id: str):
        self.accession_id = accession_id
        self._packed_id = self._pack_id(accession_id)
        self._tax_id = None
        self._blast_db, self._blast_db_volume, self._db_offset, self._length = None, None, None, None

    def _load_accession_data(self):
        self._tax_id, db_info = self._get_db("accessions")[self._packed_id][0]
        self._blast_db = BLASTDatabase(db_info >> 8)
        self._blast_db_volume = db_info & 0xFF

    @property
    def tax_id(self):
        """
        The taxon ID associated with this sequence accession ID.
        """
        if self._tax_id is None:
            self._load_accession_data()
        return self._tax_id

    @property
    def blast_db(self):
        """
        The BLAST database in which this sequence accession ID was indexed.
        """
        if self._blast_db is None:
            self._load_accession_data()
        return self._blast_db

    @property
    def blast_db_volume(self):
        """
        The numeric BLAST database volume ID in which this sequence accession was indexed.
        """
        if self._blast_db_volume is None:
            self._load_accession_data()
        return self._blast_db_volume

    @property
    def length(self):
        """
        The length of the sequence (number of nucleotides or amino acids).
        """
        if self._length is None:
            self._length = self._get_db("accession_lengths")[self._packed_id][0][0]
        return self._length

    @property
    def db_offset(self):
        """
        The byte offset in the BLAST database volume at which this sequence starts.
        """
        if self._db_offset is None:
            self._db_offset = self._get_db("accession_offsets")[self._packed_id][0][0]
        return self._db_offset

    def _pack_id(self, accession_id):
        if accession_id.endswith(".1"):
            accession_id = accession_id[: -len(".1")]
        accession_id = accession_id.replace("_", "")
        return accession_id

    def get_from_s3(self):
        """
        Returns a file-like object streaming the nucleotide sequence for this accession from the AWS S3 NCBI BLAST
        database mirror (https://registry.opendata.aws/ncbi-blast-databases/), if available.
        """
        # FIXME: rjust value has to be 3 for some databases
        volume_id_length = 2 if self.blast_db.name in {"ref_prok_rep_genomes", "Betacoronavirus"} else 3
        blast_db = f"{self.blast_db.name}.{str(self.blast_db_volume).rjust(3, '0')}"
        if self.blast_db.name == "ref_viruses_rep_genomes":
            blast_db = f"{self.blast_db.name}"
        else:
            volume_id_length = 2 if self.blast_db.name in {"ref_prok_rep_genomes", "Betacoronavirus"} else 3
            blast_db = f"{self.blast_db.name}.{str(self.blast_db_volume).rjust(volume_id_length, '0')}"
        s3_url = f"https://{self.s3_host}/{accession_db.db_timestamp}/{blast_db}.nsq"
        headers = {"Range": f"bytes={self.db_offset}-{self.db_offset + (self.length // 4)}"}
        res = self.http.request("GET", s3_url, headers=headers, preload_content=False)
        if res.status // 100 != 2:
            raise TaxoniqException(f"Error while retrieving {s3_url}: {res.status} {res.reason}")
        res._decoder = NcbiNa2Decoder(self.length)
        return res

    def get_from_gs(self):
        """
        Returns a file-like object streaming the nucleotide sequence for this accession from the Google Storage NCBI
        BLAST database mirror (https://registry.opendata.aws/ncbi-blast-databases/), if available.
        """
        raise NotImplementedError()

    def url(self):
        """
        Returns the HTTPS URL for the NCBI GenBank web page representing this sequence accession ID.
        """
        return f"https://www.ncbi.nlm.nih.gov/nuccore/{self.accession_id}"

    def __eq__(self, other):
        return self.accession_id == other.accession_id

    def __repr__(self):
        return "{}.{}('{}')".format(self.__module__, self.__class__.__name__, self.accession_id)


class Taxon(DatabaseService, ItemAttrAccess):
    """
    An object representing an NCBI Taxonomy taxon, identified by its taxon ID. The object can be instantiated by
    uniquely identifying a taxon using the numeric taxon ID, an alphanumeric accession ID of a sequence associated with
    the taxon ID, or the scientific name of the taxon.
    """

    # TODO: more attributes from structured metadata at species/strain level e.g. gc, ploidy, ...
    _db_dir = ncbi_taxon_db.db_dir
    _db_files = {
        "taxa": (RecordTrie("IBBB"), os.path.join(_db_dir, "taxa.marisa")),
        "wikidata": (RecordTrie("I"), os.path.join(_db_dir, "wikidata.marisa")),
        "sn2t": (RecordTrie("I"), os.path.join(_db_dir, "sn2taxid.marisa")),
    }
    _string_index_names = (
        "scientific_name",
        "common_name",
        "taxid2refrep",
        "taxid2refseq",
        "description",
        "en_wiki_title",
        "child_nodes",
        "host",
    )
    for _string_index in _string_index_names:
        _db_files[_string_index] = (zstandard, os.path.join(_db_dir, _string_index + ".zstd"))
        _db_files[_string_index + "_pos"] = (RecordTrie("I"), os.path.join(_db_dir, _string_index + ".marisa"))

    common_ranks = {
        Rank[i] for i in ("species", "genus", "family", "order", "class", "phylum", "kingdom", "superkingdom")
    }

    def __init__(self, tax_id: int = None, accession_id: str = None, scientific_name: str = None):
        if sum(x is not None for x in (tax_id, accession_id, scientific_name)) != 1:
            raise TaxoniqException("Expected exactly one of tax_id, accession_id, or scientific_name to be set")
        if tax_id is not None:
            self.tax_id = int(tax_id)
        elif accession_id is not None:
            self.tax_id = Accession(accession_id).tax_id
        elif scientific_name is not None:
            self.tax_id = self._get_db("sn2t")[scientific_name][0][0]
        self._parent, rank, self.division_id, self.specified_species = self._get_db("taxa")[str(self.tax_id)][0]
        self._rank = Rank(rank)
        self._str_attr_cache = {}

    def _get_str_attr(self, attr_name):
        if attr_name not in self._str_attr_cache:
            pos_db = self._get_db(attr_name + "_pos")
            str_db = self._get_db(attr_name)
            try:
                pos = pos_db[str(self.tax_id)][0][0]
            except KeyError:
                raise NoValue(f'The taxon {self} has no value indexed for "{attr_name}"')
            self._str_attr_cache[attr_name] = str_db[pos : str_db.index(b"\n", pos)].decode()
        return self._str_attr_cache[attr_name]

    @property
    def rank(self) -> Rank:
        """
        Rank of the taxon. See https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7408187/#sec9title for more details.
        """
        return self._rank

    @property
    def scientific_name(self) -> str:
        """
        The unique scientific name of the taxon.
        """
        return self._get_str_attr("scientific_name")

    @property
    def common_name(self) -> str:
        """
        Common name of the taxon. In taxoniq, this is defined as the NCBI taxonomy blast name if available, or the
        genbank common name if available, or the first listed common name. See
        https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3245000/ for definitions of these fields.
        """
        return self._get_str_attr("common_name")

    @property
    def lineage(self) -> "List[Taxon]":
        """
        Lineage for this taxon (the list of parent nodes from the taxon to the root of the taxonomic tree).
        """
        lineage = [self]
        while lineage[-1].tax_id != 1:
            lineage.append(Taxon(lineage[-1]._parent))
        return lineage

    @property
    def ranked_lineage(self) -> "List[Taxon]":
        """
        Lineage of main taxonomic ranks (species, genus, family, order, class, phylum, kingdom, superkingdom).
        """
        return list(filter(lambda t: t.rank in self.common_ranks, self.lineage))

    @property
    def parent(self) -> "Union[Taxon, None]":
        """
        The parent taxon for this taxon.

        For the root of the tree, `parent` is `None`.
        """
        if self.tax_id == 0:
            return None
        else:
            return Taxon(self._parent)

    @property
    def child_nodes(self) -> "List[Taxon]":
        """
        Returns a list of taxon objects that list this taxon as their parent.
        """
        return [Taxon(int(t)) for t in self._get_str_attr("child_nodes").split(",")]

    @property
    def ranked_child_nodes(self) -> "List[Taxon]":
        """
        List of child nodes in the next main taxonomic rank (species, genus, family, order, class, phylum, kingdom,
        superkingdom).
        """
        return list(filter(lambda t: t.rank in self.common_ranks, self.child_nodes))

    @property
    def description(self) -> str:
        """
        Introductory paragraph for this taxon from English Wikipedia, if available.
        """
        try:
            return self._get_str_attr("description")
        except KeyError:
            return ""

    @property
    def best_available_description(self):
        """
        Introductory paragraph from English Wikipedia for this taxon or the first parent taxon where a description is
        available.
        """
        t = self
        while t.tax_id != 1:
            if t.description:
                return t.description
            t = t.parent
        return ""

    @property
    def best_refseq_taxon(self):
        """
        Best related taxon with refseq representative genome sequence available.
        For viruses, this is the RefSeq "genome neighbor" as defined in
        https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4383986/ and retrieved from
        https://ftp.ncbi.nlm.nih.gov/genomes/Viruses/Viruses_RefSeq_and_neighbors_genome_data.tab.
        For other domains, this is the RefSeq representative genome for the taxon's species, if available, as
        seen in the species_taxid column of https://ftp.ncbi.nlm.nih.gov/genomes/refseq/assembly_summary_refseq.txt.

        The accessions for the genome can be accessed as follows:

            Taxon(123).best_refseq_taxon.refseq_representative_genome_accessions
        """
        raise NotImplementedError()

    @property
    def host(self) -> List[str]:
        """
        A text description of a symbiont host or hosts for this taxon's organism, if any.
        """
        return self._get_str_attr("host").split(",")

    @property
    def refseq_representative_genome_accessions(self) -> List[Accession]:
        """
        A list of :class:`Accession` objects for sequences in the RefSeq representative genome assembly for this
        taxon, if available.
        """
        return [Accession(i) for i in self._get_str_attr("taxid2refrep").split(",")]

    @property
    def refseq_genome_accessions(self) -> List[Accession]:
        """
        A list of :class:`Accession` objects for sequences in the most recent RefSeq genome assembly for this
        taxon, if available.
        """
        return [Accession(i) for i in self._get_str_attr("taxid2refseq").split(",")]

    @classmethod
    def lca(cls, taxa):
        """
        Given a list of Taxon objects, returns the last common ancestor taxon.
        """
        raise NotImplementedError()

    @classmethod
    def distance(cls, taxa):
        """
        Phylogenetic distance between taxa as computed by WoL
        """
        raise NotImplementedError()

    def closest_taxon_with_refseq_genome(self):
        """
        Returns a taxon closest by phylogenetic distance as computed by WoL and with a refseq genome associated
        """
        pass

    @property
    def url(self):
        """
        Returns the HTTPS URL for the NCBI Taxonomy web page representing this taxon.
        """
        return f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?mode=Info&id={self.tax_id}"

    @property
    def wikidata_id(self):
        """
        Wikidata ID for this taxon.
        """
        wikidata_id = self._get_db("wikidata")[str(self.tax_id)][0][0]
        return f"Q{wikidata_id}"

    @property
    def wikidata_url(self):
        """
        URL of the Wikidata web page representing this taxon.
        """
        if self.wikidata_id:
            return f"https://www.wikidata.org/wiki/{self.wikidata_id}"

    def __eq__(self, other):
        return self.tax_id == other.tax_id

    def __repr__(self):
        return "{}.{}({})".format(self.__module__, self.__class__.__name__, self.tax_id)
