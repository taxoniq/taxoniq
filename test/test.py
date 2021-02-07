#!/usr/bin/env python3

import os
import sys
import unittest
import uuid
import tempfile
import time
import logging

import taxoniq

logging.basicConfig(level=logging.DEBUG)


class TestTaxoniq(unittest.TestCase):
    def test_taxon_interface(self):
        t = taxoniq.Taxon(9606)
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


if __name__ == "__main__":
    unittest.main()
