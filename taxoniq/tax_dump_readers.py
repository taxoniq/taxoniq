import enum

from . import Rank


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
        ("inherited_HGC", int, "flag (1 or 0); 1 if node inherits hydrogenosome gencode from parent"),
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
        ("name_class", str, "(synonym, common name, ...)", enum.Enum),
    ]


class DivisionsReader(TaxDumpReader):
    table_name = "division"
    fields = [
        ("division_id", int, "taxonomy database division id"),
        ("division_code", str, "GenBank division code (three characters) e.g. BCT, PLN, VRT, MAM, PRI.."),
        ("division_name", str),
        ("comments", str),
    ]


class GeneticCodeReader(TaxDumpReader):
    table_name = "gencode"
    fields = [
        ("genetic_code", int, "GenBank genetic code id"),
        ("abbreviation", str, "genetic code name abbreviation"),
        ("name", str, "genetic code name"),
        ("cde", str, "translation table for this genetic code"),
        ("starts", str, "start codons for this genetic code"),
    ]


class DeletedNodesReader(TaxDumpReader):
    table_name = "delnodes"
    fields = [("tax_id", int, "deleted node id")]


class MergedNodesReader(TaxDumpReader):
    table_name = "merged"
    fields = [
        ("old_tax_id", int, "id of nodes which has been merged"),
        ("new_tax_id", int, "id of nodes which is result of merging"),
    ]


class CitationsReader(TaxDumpReader):
    table_name = "citations"
    fields = [
        ("cit_id", int, "the unique id of citation"),
        ("cit_key", str, "citation key"),
        ("medline_id", int, "unique id in MedLine database (0 if not in MedLine)"),
        ("pubmed_id", int, "unique id in PubMed database (0 if not in PubMed)"),
        ("url", str, "URL associated with citation"),
        (
            "text",
            str,
            """any text (usually article name and authors); The following characters are escaped in this text
                         by a backslash: newline (appear as "\n"), tab character ("\t"), double quotes ('\"'),
                         backslash character ("\\").""",
        ),
        ("taxid_list", str, "list of node ids separated by a single space"),
    ]


class TypeOfTypeReader(TaxDumpReader):
    table_name = "typeoftype"
    fields = [
        ("type_name", str, "name of type material type"),
        ("synonyms", str, "alternative names for type material type"),
        (
            "nomenclature",
            str,
            """Taxonomic Code of Nomenclature coded by a single letter:
                                 -- B - International Code for algae, fungi and plants (ICN), previously Botanical Code,
                                 -- P - International Code of Nomenclature of Prokaryotes (ICNP),
                                 -- Z - International Code of Zoological Nomenclature (ICZN),
                                 -- V - International Committee on Taxonomy of Viruses (ICTV) virus classification.""",
        ),
        ("description", str, "descriptive text"),
    ]


class HostReader(TaxDumpReader):
    table_name = "host"
    fields = [("tax_id", str, "node id"), ("potential_hosts", str, "theoretical host list separated by comma ','")]


class TypeMaterialReader(TaxDumpReader):
    table_name = "typematerial"
    fields = [
        ("tax_id", int, "node id"),
        ("tax_name", str, "organism name type material is assigned to"),
        ("type", str, "type material type (see typeoftype.dmp)"),
        ("identifier", str, "identifier in type material collection"),
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
        ("superkingdom_name", str, "superkingdom (domain) name when available"),
    ]


class FullNameLineageReader(TaxDumpReader):
    table_name = "fullnamelineage"
    fields = [
        ("tax_id", int, "node id"),
        ("tax_name", str, "scientific name of the organism"),
        (
            "lineage",
            str,
            (
                "sequence of ancestor names separated by semicolon ';' denoting nodes' ancestors starting "
                "from the most distant one and ending with the immediate one"
            ),
        ),
    ]


class TaxIdLineageReader(TaxDumpReader):
    table_name = "taxidlineage"
    fields = [
        ("tax_id", int, "node id"),
        (
            "lineage",
            str,
            (
                "sequence of node ids separated by space denoting nodes' ancestors starting from the most "
                "distant one and ending with the immediate one"
            ),
        ),
    ]
