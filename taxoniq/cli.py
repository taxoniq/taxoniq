import json
import logging
import argparse

from . import Taxon
from .version import __version__


def print_json(data, output_format):
    def formatter(i):
        if output_format:
            return output_format.format_map(i)
        return repr(i)
    print(json.dumps(data, indent=4, default=formatter))


parser = argparse.ArgumentParser(prog="taxoniq")
parser.add_argument("--version", action="version", version=__version__)
parser.add_argument("operation", choices=[attr for attr in dir(Taxon) if not attr.startswith("_")])
parser.add_argument("--taxon-id", help="Numeric NCBI taxon ID")
parser.add_argument("--accession-id", help="Alphanumeric NCBI sequence accession ID")
parser.add_argument("--scientific-name", help="Unique scientific name of the taxon")
parser.add_argument("--output-format", help=("Format string for Taxon or Accession objects, e.g. {scientific_name} "
                                             "will return a taxon's scientific name for each taxon in the results"))


def cli():
    """
    Taxoniq: Taxon Information Query - fast, offline querying of NCBI Taxonomy and related data

    Run "taxoniq COMMAND --help" for command-specific usage and options.
    """
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if sum([int(bool(i)) for i in (args.taxon_id, args.accession_id, args.scientific_name)]) != 1:
        raise argparse.ArgumentError("Expected exactly one of --taxon-id, --accession-id, or --scientific-name")
    taxon = Taxon(tax_id=args.taxon_id, accession_id=args.accession_id, scientific_name=args.scientific_name)
    print_json(getattr(taxon, args.operation), output_format=args.output_format)
