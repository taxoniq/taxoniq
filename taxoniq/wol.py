import csv


class WOLReader:
    def __init__(self):
        from ete3 import Tree
        self.tree = Tree("wol/astral.cons.nid.e5p50.nwk", format=1)
        # see http://etetoolkit.org/docs/latest/tutorial/tutorial_trees.html#getting-distances-between-nodes
        # load metadata, store wol id -> taxid mapping
        # traverse tree, for each node, record (taxid, node.up, node.dist)
        # Q: species_taxid?
        # Q: mapping WOL internal nodes to taxonomy internal nodes?
        # Q: nearest neighbor queries?

        with open("wol/metadata.tsv") as fh:
            for line in csv.DictReader(fh, dialect="excel-tab"):
                node = self.tree.search_nodes(name=line["#genome"])[0]
                print(line["#genome"], line["taxid"], line["species_taxid"], node.up.name, node.dist)
