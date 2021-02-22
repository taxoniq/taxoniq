import json
import logging

import click

from . import Taxon
from .version import __version__


def print_json(data, output_format):
    def formatter(i):
        if output_format:
            return output_format.format_map(i)
        return repr(i)
    print(json.dumps(data, indent=4, default=formatter))


@click.command()
@click.version_option(version=__version__)
@click.argument("operation", type=click.Choice([attr for attr in dir(Taxon) if not attr.startswith("_")]))
@click.option("--taxon-id", help="Numeric NCBI taxon ID")
@click.option("--accession-id", help="Alphanumeric NCBI sequence accession ID")
@click.option("--scientific-name", help="Unique scientific name of the taxon")
@click.option("--output-format", help=("Format string for Taxon or Accession objects, e.g. {scientific_name} will "
                                       "return a taxon's scientific name for each taxon in the results"))
def cli(operation, taxon_id=None, accession_id=None, scientific_name=None, output_format=None):
    """
    Taxoniq: Taxon Information Query - fast, offline querying of NCBI Taxonomy and related data

    Run "taxoniq COMMAND --help" for command-specific usage and options.
    """
    logging.basicConfig(level=logging.INFO)

    if sum([int(bool(i)) for i in (taxon_id, accession_id, scientific_name)]) != 1:
        raise click.UsageError("Expected exactly one of --taxon-id, --accession-id, or --scientific-name")
    taxon = Taxon(tax_id=taxon_id, accession_id=accession_id, scientific_name=scientific_name)
    print_json(getattr(taxon, operation), output_format=output_format)
