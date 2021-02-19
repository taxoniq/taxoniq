#!/usr/bin/env python3

import os
import json
import unittest
import logging
from concurrent.futures import ThreadPoolExecutor

import taxoniq
import taxoniq.build

logging.basicConfig(level=logging.DEBUG)


class TestTaxoniq(unittest.TestCase):
    def test_taxon_interface(self):
        t2 = taxoniq.Taxon(accession_id="NC_000913.3")
        self.assertEqual(t2, taxoniq.Taxon(511145))
        self.assertEqual(t2, taxoniq.Taxon(scientific_name="Escherichia coli str. K-12 substr. MG1655"))
        self.assertEqual(t2.scientific_name, "Escherichia coli str. K-12 substr. MG1655")
        self.assertEqual(t2.parent.parent.common_name, "E. coli")
        self.assertEqual(t2.ranked_lineage, [taxoniq.Taxon(562), taxoniq.Taxon(561), taxoniq.Taxon(543),
                                             taxoniq.Taxon(91347), taxoniq.Taxon(1236), taxoniq.Taxon(1224),
                                             taxoniq.Taxon(2)])

    @unittest.skipIf("CI" in os.environ, "Skippinng test that requires eukaryotic database")
    def test_eukaryote_taxon_interface(self):
        t = taxoniq.Taxon(accession_id="NC_000001.11")
        self.assertEqual(t, taxoniq.Taxon(9606))
        self.assertEqual(t.scientific_name, "Homo sapiens")
        self.assertEqual(t.common_name, "human")
        self.assertEqual(t.parent, taxoniq.Taxon(9605))
        self.assertEqual(t.ranked_lineage, [taxoniq.Taxon(scientific_name='Homo sapiens'),
                                            taxoniq.Taxon(scientific_name='Homo'),
                                            taxoniq.Taxon(scientific_name='Hominidae'),
                                            taxoniq.Taxon(scientific_name='Primates'),
                                            taxoniq.Taxon(scientific_name='Mammalia'),
                                            taxoniq.Taxon(scientific_name='Chordata'),
                                            taxoniq.Taxon(scientific_name='Metazoa'),
                                            taxoniq.Taxon(scientific_name='Eukaryota')])

    def test_accession_interface(self):
        a = taxoniq.Accession(accession_id="NC_000913.3")
        self.assertEqual(a.length, 4641652)
        self.assertEqual(a.tax_id, 511145)
        with a.get_from_s3() as fh:
            seq = fh.read()
            assert seq.startswith(b"AGCTTTTCATTCTGACTGCAACGGGCAATATGTCTCTGTGTGGATTAAAAAAAGAGTGTCTGATAGCAGCT")
            assert seq.endswith(b"AATGTTGCACCGTTTGCTGCATGATATTGAAAAAAATATCACCAAATAAAAAACGCCTTAGTAAGTATTTTTC")
            self.assertEqual(fh.read(), b"")
        with a.get_from_s3() as fh:
            self.assertEqual(fh.read(1), b"AGCT")

    @unittest.skipIf("CI" in os.environ, "Skippinng test that requires eukaryotic database")
    def test_eukaryote_accession_interface(self):
        a = taxoniq.Accession(accession_id="NC_000001.11")
        self.assertEqual(a.length, 248956420)
        self.assertEqual(a.tax_id, 9606)
        a = taxoniq.Accession(accession_id="NZ_CP019573.1")
        self.assertEqual(a.length, 1745788)
        self.assertEqual(a.tax_id, 1817405)

    @unittest.skipIf("CI" in os.environ, "Skippinng test that requires eukaryotic database")
    def test_taxon2refseq(self):
        def fetch_seq(accession):
            seq = accession.get_from_s3().read()
            return (accession, seq)
        taxon = taxoniq.Taxon(scientific_name="Apis mellifera")
        for accession, seq in ThreadPoolExecutor().map(fetch_seq, taxon.refseq_representative_genome_accessions):
            assert accession.length == len(seq)

    def test_wikipedia_client(self):
        client = taxoniq.build.WikipediaDescriptionClient()
        result_file = client.build_index(destdir="/tmp", max_records=2)
        with open(result_file) as fh:
            for line in fh:
                doc = json.loads(line)
                for key in "taxid", "wikidata_id", "en_wiki_title", "extract":
                    self.assertIn(key, doc)


if __name__ == "__main__":
    unittest.main()
