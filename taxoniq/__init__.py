import os
from typing import List
from enum import Enum

import marisa_trie
import zstandard

Rank = Enum(
    "Rank",
    ("biotype clade class cohort family forma forma_specialis genotype genus infraclass infraorder isolate kingdom "
     "morph order parvorder pathogroup phylum section series serogroup serotype species species_group species_subgroup "
     "strain subclass subcohort subfamily subgenus subkingdom suborder subphylum subsection subspecies subtribe "
     "subvariety superclass superfamily superkingdom superorder superphylum tribe varietas no_rank")
)


class TaxoniqException(Exception):
    pass


class Accession:
    def url(self):
        raise NotImplementedError()


class Taxon:
    """
    FIXME: add docstring
    """
    _databases = {}
    _db_files = {
        "taxa": (marisa_trie.RecordTrie("IBBB"), os.path.join(os.path.dirname(__file__), "taxa.marisa")),
        "a2t": (marisa_trie.RecordTrie("I"), os.path.join(os.path.dirname(__file__), "accession2taxid.marisa")),
        "sn2t": (marisa_trie.RecordTrie("I"), os.path.join(os.path.dirname(__file__), "sn2taxid.marisa")),
        "scientific_names_pos": (marisa_trie.RecordTrie("I"), os.path.join(os.path.dirname(__file__), "scientific_names_pos.marisa")),
        "scientific_names": (zstandard, os.path.join(os.path.dirname(__file__), "scientific_names.zstd")),
        "common_names_pos": (marisa_trie.RecordTrie("I"), os.path.join(os.path.dirname(__file__), "common_names_pos.marisa")),
        "common_names": (zstandard, os.path.join(os.path.dirname(__file__), "common_names.zstd")),
    }
    common_ranks = {Rank[i] for i in ("species", "genus", "family", "order", "class", "phylum", "kingdom", "superkingdom")}

    def __init__(self, tax_id: int = None, accession_id: str = None, scientific_name: str = None):
        if sum(x is not None for x in (tax_id, accession_id, scientific_name)) != 1:
            raise TaxoniqException("Expected exactly one of tax_id, accession_id, or scientific_name to be set")
        if tax_id is not None:
            self.tax_id = tax_id
        elif accession_id is not None:
            self.tax_id = self._get_db("a2t")[accession_id][0][0]
        elif scientific_name is not None:
            self.tax_id = self._get_db("sn2t")[scientific_name][0][0]
        self._parent, rank, self.division_id, self.specified_species = self._get_db("taxa")[str(self.tax_id)][0]
        self.rank = Rank(rank)
        self._str_attr_cache = {}

    def _pack_accession_id(self, accession_id):
        if accession_id.endswith(".1"):
            accession_id = accession_id[:-len(".1")]
        # TODO: drop _ or _0+
        return accession_id

    def _get_db(self, db_name):
        if db_name not in self._databases:
            db_type, filename = self._db_files[db_name]
            if db_type == zstandard:
                with open(filename, "rb") as fh:
                    self._databases[db_name] = zstandard.decompress(fh.read())
            else:
                self._databases[db_name] = db_type.mmap(filename)
        return self._databases[db_name]

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
        Lineage of well-established taxonomic ranks (species, genus, family, order, class, phylum, kingdom, superkingdom)
        '''
        return list(filter(lambda t: t.rank in self.common_ranks, self.lineage))

    @property
    def parent(self) -> 'Taxon':
        return Taxon(self._parent)

    @property
    def description(self) -> str:
        '''
        Opening paragraph on Wikipedia
        '''
        raise NotImplementedError()

    @property
    def refseq_reference_genome_accessions(self) -> List[Accession]:
        raise NotImplementedError()

    @property
    def refseq_representative_genome_accessions(self) -> List[Accession]:
        raise NotImplementedError()

    def url(self):
        '''
        URL of the NCBI Taxonomy web page for this taxon
        '''
        raise NotImplementedError()

    def __eq__(self, other):
        return self.tax_id == other.tax_id

    def __repr__(self):
        return "{}.{}({})".format(self.__module__, self.__class__.__name__, self.tax_id)
