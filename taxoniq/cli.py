"""
Taxoniq: Taxon Information Query - fast, offline querying of NCBI Taxonomy and related data

Run "taxoniq COMMAND --help" for command-specific usage and options.

If an error occurs, Taxoniq will exit with code 4 when the error is due to a missing taxon or accession ID,
or code 1 for all other errors.
"""
import argparse
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from . import Accession, Taxon, __version__, accession_db, ncbi_taxon_db


def print_json(data, output_format):
    def formatter(i):
        if output_format:
            return output_format.format_map(i)
        if isinstance(i, Taxon):
            return i.tax_id
        if isinstance(i, Accession):
            return i.accession_id
        return repr(i)

    print(json.dumps(data, indent=4, default=formatter))


def get_version():
    return (
        f"Taxoniq {__version__}\n"
        f"Taxonomy DB: {ncbi_taxon_db.db_timestamp} ({os.path.dirname(ncbi_taxon_db.__file__)})\n"
        f"BLAST DB: {accession_db.db_timestamp} ({os.path.dirname(accession_db.__file__)})"
    )


class TaxoniqHelpFormatter(argparse.RawTextHelpFormatter):
    def add_argument(self, action):
        if action.dest == "operation":
            for choice in action.choices:
                self._add_item(self._format_text, [self._prog + " " + choice])
                docstring = getattr(Taxon, choice, getattr(Accession, choice, "")).__doc__.strip()
                self._add_item(self._format_text, [" " * self._current_indent * 4 + docstring])


parser = argparse.ArgumentParser(prog="taxoniq", description=__doc__, formatter_class=TaxoniqHelpFormatter)
parser.add_argument("--version", action="version", version=get_version())
parser.add_argument(
    "operation",
    choices=[attr.replace("_", "-") for attr in dir(Taxon) if not attr.startswith("_")]
    + ["get-from-s3", "get-from-gs"],
)
parser.add_argument("--taxon-id", help="Numeric NCBI taxon ID")
parser.add_argument("--accession-id", help="Alphanumeric NCBI sequence accession ID")
parser.add_argument("--scientific-name", help="Unique scientific name of the taxon")
parser.add_argument(
    "--output-format",
    help=(
        "Format string for Taxon or Accession objects, e.g. {scientific_name} "
        "will return a taxon's scientific name for each taxon in the results"
    ),
)


def exit_not_found_err(args):
    if args.taxon_id:
        msg = f"Taxon ID {args.taxon_id} not found"
    elif args.accession_id:
        msg = f"Accession ID {args.accession_id} not found"
    else:
        msg = f'Taxon ID not found for "{args.scientific_name}"'
    print(msg + "\n" + get_version(), file=sys.stderr)
    exit(4)


def cli(args=None):
    args = parser.parse_args(args)
    logging.basicConfig(level=logging.INFO)

    if sum([int(bool(i)) for i in (args.taxon_id, args.accession_id, args.scientific_name)]) != 1:
        raise argparse.ArgumentError(None, "Expected exactly one of --taxon-id, --accession-id, or --scientific-name")
    if args.operation in {"get-from-s3", "get-from-gs"}:
        if not args.accession_id:
            raise argparse.ArgumentError(None, "This operation requires an accession ID.")
        if args.accession_id == "-":

            def fetch_seq(accession_id):
                try:
                    acc = Accession(accession_id)
                    op = getattr(acc, args.operation.replace("-", "_"))
                    seq = op().read()
                except KeyError:
                    args.accession_id = accession_id
                    exit_not_found_err(args)
                return (acc, seq)

            with ThreadPoolExecutor() as executor:
                for accession, sequence in executor.map(fetch_seq, sys.stdin.read().splitlines()):
                    print(">" + accession.accession_id)
                    sys.stdout.flush()
                    for line_start in range(0, len(sequence), 64):
                        sys.stdout.buffer.write(sequence[line_start : line_start + 64])
                        sys.stdout.buffer.write(b"\n")
                    sys.stdout.flush()
        else:
            accession = Accession(args.accession_id)
            operation = getattr(accession, args.operation.replace("-", "_"))
            try:
                with operation() as fh:
                    print(">" + accession.accession_id)
                    sys.stdout.flush()
                    for chunk in fh.stream():
                        for line_start in range(0, len(chunk), 64):
                            sys.stdout.buffer.write(chunk[line_start : line_start + 64])
                            sys.stdout.buffer.write(b"\n")
                        sys.stdout.flush()
            except KeyError:
                exit_not_found_err(args)
    else:
        try:
            taxon = Taxon(tax_id=args.taxon_id, accession_id=args.accession_id, scientific_name=args.scientific_name)
        except KeyError:
            exit_not_found_err(args)
        print_json(getattr(taxon, args.operation.replace("-", "_")), output_format=args.output_format)
