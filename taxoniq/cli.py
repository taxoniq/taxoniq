import sys
import json
import logging
import argparse
from concurrent.futures import ThreadPoolExecutor

from . import Taxon, Accession
from .version import __version__


def print_json(data, output_format):
    def formatter(i):
        if output_format:
            return output_format.format_map(i)
        if isinstance(i, Taxon):
            return i.taxon_id
        if isinstance(i, Accession):
            return i.accession_id
        return repr(i)
    print(json.dumps(data, indent=4, default=formatter))


parser = argparse.ArgumentParser(prog="taxoniq")
parser.add_argument("--version", action="version", version=__version__)
parser.add_argument("operation",
                    choices=[attr for attr in dir(Taxon) if not attr.startswith("_")] + ["get_from_s3", "get_from_gs"])
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
    if args.operation in {"get_from_s3", "get_from_gs"}:
        if not args.accession_id:
            raise argparse.ArgumentError("This operation requires an accession ID.")
        if args.accession_id == "-":
            def fetch_seq(accession_id):
                accession = Accession(accession_id)
                op = getattr(accession, args.operation)
                seq = op().read()
                return (accession, seq)

            with ThreadPoolExecutor() as executor:
                for accession, seq in executor.map(fetch_seq, sys.stdin.read().splitlines()):
                    print(">" + accession.accession_id)
                    sys.stdout.flush()
                    for line_start in range(0, len(seq), 64):
                        sys.stdout.buffer.write(seq[line_start:line_start+64])
                        sys.stdout.buffer.write(b"\n")
        else:
            accession = Accession(args.accession_id)
            operation = getattr(accession, args.operation)
            print(">" + accession.accession_id)
            sys.stdout.flush()
            with operation() as fh:
                for chunk in fh.stream():
                    for line_start in range(0, len(chunk), 64):
                        sys.stdout.buffer.write(chunk[line_start:line_start+64])
                        sys.stdout.buffer.write(b"\n")
    else:
        taxon = Taxon(tax_id=args.taxon_id, accession_id=args.accession_id, scientific_name=args.scientific_name)
        print_json(getattr(taxon, args.operation), output_format=args.output_format)
