#!/usr/bin/env python3

import os
import sys
import unittest
import logging
from concurrent.futures import ThreadPoolExecutor

import taxoniq

logging.basicConfig(level=logging.DEBUG)


class TestTaxoniq(unittest.TestCase):
    def test_taxon_interface(self):
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

        t2 = taxoniq.Taxon(accession_id="NC_000913.3")
        self.assertEqual(t2, taxoniq.Taxon(511145))
        self.assertEqual(t2, taxoniq.Taxon(scientific_name="Escherichia coli str. K-12 substr. MG1655"))
        self.assertEqual(t2.scientific_name, "Escherichia coli str. K-12 substr. MG1655")
        self.assertEqual(t2.parent.parent.common_name, "E. coli")

    def test_accession_interface(self):
        a = taxoniq.Accession(accession_id="NC_000001.11")
        self.assertEqual(a.length, 248956420)
        self.assertEqual(a.tax_id, 9606)
        a = taxoniq.Accession(accession_id="NZ_CP019573.1")
        self.assertEqual(a.length, 1745788)
        self.assertEqual(a.tax_id, 1817405)
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

    def test_taxon2refseq(self):
        def fetch_seq(accession_id):
            accession = taxoniq.Accession(accession_id)
            seq = accession.get_from_s3().read()
            return (accession, seq)
        taxon = taxoniq.Taxon(scientific_name="Apis mellifera")
        for accession, seq in ThreadPoolExecutor().map(fetch_seq, taxon.refseq_representative_genome_accessions):
            assert accession.length == len(seq)


if __name__ == "__main__":
    unittest.main()
