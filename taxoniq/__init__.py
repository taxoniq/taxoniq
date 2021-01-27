from typing import List

Rank = enum.Enum(
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
        "sn_pos": (marisa_trie.RecordTrie("I"), os.path.join(os.path.dirname(__file__), "scientific_names.marisa")),
        "sn": (zstandard, os.path.join(os.path.dirname(__file__), "scientific_names.zstd")),
        "cn_pos": (marisa_trie.RecordTrie("I"), os.path.join(os.path.dirname(__file__), "common_names.marisa")),
        "cn": (zstandard, os.path.join(os.path.dirname(__file__), "common_names.zstd")),
    }

    def __init__(self, tax_id=None, accession_id=None, scientific_name=None):
        if sum(x is not None for x in (tax_id, accession_id, scientific_name)) != 1:
            raise TaxoniqException("Expected exactly one of tax_id, accession_id, or scientific_name to be set")
        if tax_id is not None:
            self.tax_id = tax_id
        elif accession_id is not None:
            taxon = a2t[accession][0][0]

    def _pack_accession_id(self):
        if accession.endswith(".1"):
            accession = accession[:-len(".1")]

    def _get_db(self, db_name):
        pass

    def _get_sn(self, pos):
        return sn_str[pos:sn_str.index(b"\n", pos)].decode()

    @property
    def rank(self) -> Rank:
        pass

    @property
    def scientific_name(self) -> str:
        pass

    @property
    def common_name(self) -> str:
        '''
        Common name of the taxon. In taxoniq, this is defined as the NCBI taxonomy blast name if available, or the
        genbank common name if available, or the first listed common name. See
        https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3245000/ for definitions of these fields.
        '''
        pass

    @property
    def lineage(self) -> List[Taxon]:
        while True:
            parent, rank, division_id, specified_species = taxa[str(taxon)][0]
            print(taxon, parent, Rank(rank), division_id, specified_species, get_sn(sn_pos[str(taxon)][0][0]))
            if taxon == "1":
                break
            taxon = str(parent)

    @property
    def ranked_lineage(self) -> List[Taxon]:
        '''
        Lineage of well-established taxonomic ranks (species, genus, family, order, class, phylum, kingdom, superkingdom)
        '''
        pass

    @property
    def description(self) -> str:
        '''
        Opening paragraph on Wikipedia
        '''
        raise NotImplementedError()

    @property
    def has_refseq(self) -> bool:
        raise NotImplementedError()

    @property
    def refseq_accessions(self) -> List[Accession]:
        raise NotImplementedError()

    def url(self):
        '''
        URL of the NCBI Taxonomy web page for this taxon
        '''
        raise NotImplementedError()

    def __repr__(self):
        return repr(self)
