import os
from typing import List
from enum import Enum

import urllib3
import zstandard
from marisa_trie import RecordTrie

import taxoniq_accessions
import taxoniq_accession_offsets
import taxoniq_accession_lengths
from .const import blast_db_timestamp
from .util import TwoBitDecoder

Rank = Enum(
    "Rank",
    ("biotype clade class cohort family forma forma_specialis genotype genus infraclass infraorder isolate kingdom "
     "morph order parvorder pathogroup phylum section series serogroup serotype species species_group species_subgroup "
     "strain subclass subcohort subfamily subgenus subkingdom suborder subphylum subsection subspecies subtribe "
     "subvariety superclass superfamily superkingdom superorder superphylum tribe varietas no_rank")
)


BLASTDatabase = Enum("BLASTDatabase",
                     ("ref_viruses_rep_genomes ref_prok_rep_genomes ref_euk_rep_genomes Betacoronavirus nt"))


class TaxoniqException(Exception):
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


class Accession(DatabaseService):
    """
    FIXME: add docstring
    """
    _db_files = {
        "accessions": (RecordTrie("IH"), taxoniq_accessions.db),
        "accession_offsets": (RecordTrie("I"), taxoniq_accession_offsets.db),
        "accession_lengths": (RecordTrie("I"), taxoniq_accession_lengths.db)
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
        self._blast_db_volume = db_info & 0xff

    @property
    def tax_id(self):
        if self._tax_id is None:
            self._load_accession_data()
        return self._tax_id

    @property
    def blast_db(self):
        if self._blast_db is None:
            self._load_accession_data()
        return self._blast_db

    @property
    def blast_db_volume(self):
        if self._blast_db_volume is None:
            self._load_accession_data()
        return self._blast_db_volume

    @property
    def length(self):
        if self._length is None:
            self._length = self._get_db("accession_lengths")[self._packed_id][0][0]
        return self._length

    @property
    def db_offset(self):
        if self._db_offset is None:
            self._db_offset = self._get_db("accession_offsets")[self._packed_id][0][0]
        return self._db_offset

    def _pack_id(self, accession_id):
        if accession_id.endswith(".1"):
            accession_id = accession_id[:-len(".1")]
        accession_id = accession_id.replace("_", "")
        return accession_id

    def get_from_s3(self):
        """
        Returns a file-like object streaming the nucleotide sequence for this accession from the AWS S3 NCBI BLAST
        database mirror (https://registry.opendata.aws/ncbi-blast-databases/), if available.
        """
        blast_db = f"{self.blast_db.name}.{str(self.blast_db_volume).rjust(2, '0')}"
        s3_url = f"https://{self.s3_host}/{blast_db_timestamp}/{blast_db}.nsq"
        headers = {"Range": f"bytes={self.db_offset}-{self.db_offset + (self.length // 4)}"}
        res = self.http.request("GET", s3_url, headers=headers, preload_content=False)
        res._decoder = TwoBitDecoder(self.length)
        return res

    def get_from_gs(self):
        raise NotImplementedError()

    def url(self):
        raise NotImplementedError()

    def __repr__(self):
        return "{}.{}('{}')".format(self.__module__, self.__class__.__name__, self.accession_id)


class Taxon(DatabaseService):
    """
    FIXME: add docstring
    """
    _db_dir = os.path.dirname(__file__)
    _db_files = {
        "taxa": (RecordTrie("IBBB"), os.path.join(_db_dir, "taxa.marisa")),
        "wikidata": (RecordTrie("I"), os.path.join(_db_dir, "wikidata.marisa")),
        "sn2t": (RecordTrie("I"), os.path.join(_db_dir, "sn2taxid.marisa")),
    }
    for string_index in "scientific_names", "common_names", "taxid2refseqs", "descriptions", "en_wiki_titles":
        _db_files[string_index] = (zstandard, os.path.join(_db_dir, string_index + ".zstd"))
        _db_files[string_index + "_pos"] = (RecordTrie("I"), os.path.join(_db_dir, string_index + ".marisa"))

    common_ranks = {
        Rank[i] for i in ("species", "genus", "family", "order", "class", "phylum", "kingdom", "superkingdom")
    }

    def __init__(self, tax_id: int = None, accession_id: str = None, scientific_name: str = None):
        if sum(x is not None for x in (tax_id, accession_id, scientific_name)) != 1:
            raise TaxoniqException("Expected exactly one of tax_id, accession_id, or scientific_name to be set")
        if tax_id is not None:
            self.tax_id = tax_id
        elif accession_id is not None:
            self.tax_id = Accession(accession_id).tax_id
        elif scientific_name is not None:
            self.tax_id = self._get_db("sn2t")[scientific_name][0][0]
        self._parent, rank, self.division_id, self.specified_species = self._get_db("taxa")[str(self.tax_id)][0]
        self.rank = Rank(rank)
        self._str_attr_cache = {}

    def _get_str_attr(self, attr_name):
        if attr_name not in self._str_attr_cache:
            pos_db = self._get_db(attr_name + "s_pos")
            str_db = self._get_db(attr_name + "s")
            pos = pos_db[str(self.tax_id)][0][0]
            self._str_attr_cache[attr_name] = str_db[pos:str_db.index(b"\n", pos)].decode()
        return self._str_attr_cache[attr_name]

    @property
    def scientific_name(self) -> str:
        return self._get_str_attr("scientific_name")

    @property
    def common_name(self) -> str:
        '''
        Common name of the taxon. In taxoniq, this is defined as the NCBI taxonomy blast name if available, or the
        genbank common name if available, or the first listed common name. See
        https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3245000/ for definitions of these fields.
        '''
        return self._get_str_attr("common_name")

    @property
    def lineage(self) -> 'List[Taxon]':
        lineage = [self]
        while lineage[-1].tax_id != 1:
            lineage.append(Taxon(lineage[-1]._parent))
        return lineage

    @property
    def ranked_lineage(self) -> 'List[Taxon]':
        '''
        Lineage of main taxonomic ranks (species, genus, family, order, class, phylum, kingdom, superkingdom)
        '''
        return list(filter(lambda t: t.rank in self.common_ranks, self.lineage))

    @property
    def parent(self) -> 'Taxon':
        return Taxon(self._parent)

    @property
    def children(self) -> 'List[Taxon]':
        raise NotImplementedError()

    @property
    def description(self) -> str:
        '''
        Introductory paragraph for this taxon from English Wikipedia, if available
        '''
        try:
            return self._get_str_attr("description")
        except KeyError:
            return ""

    @property
    def host(self) -> 'Taxon':
        raise NotImplementedError()

    @property
    def refseq_representative_genome_accessions(self) -> List[Accession]:
        return [Accession(i) for i in self._get_str_attr("taxid2refseq").split(",")]

    @classmethod
    def lca(cls, taxa):
        raise NotImplementedError()

    @classmethod
    def distance(cls, taxa):
        '''
        Phylogenetic distance between taxa as computed by WoL
        '''
        raise NotImplementedError()

    def closest_taxon_with_refseq_genome(self):
        '''
        Returns a taxon closest by phylogenetic distance as computed by WoL and with a refseq genome associated
        '''
        pass

    @property
    def url(self):
        '''
        URL of the NCBI Taxonomy web page for this taxon
        '''
        return f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?mode=Info&id={self.tax_id}"

    @property
    def wikidata_id(self):
        wikidata_id = self._get_db("wikidata")[str(self.tax_id)][0][0]
        return f"Q{wikidata_id}"

    @property
    def wikidata_url(self):
        '''
        URL of the Wikidata web page for this taxon
        '''
        if self.wikidata_id:
            return f"https://www.wikidata.org/wiki/{self.wikidata_id}"

    def __eq__(self, other):
        return self.tax_id == other.tax_id

    def __repr__(self):
        return "{}.{}({})".format(self.__module__, self.__class__.__name__, self.tax_id)
