import click
from importlib import resources
import os

from .. import base, templates

@click.group()
def cli():
    pass

@click.command()
def init():
    base_cfg = resources.read_text(templates, "base_cfg.yml")
    with open(base._cfg_file_path(), "w") as f:
        f.write(base_cfg)

@click.command()
@click.argument("bib_key")
def add(bib_key):
    base.add_entry(bib_key)

@click.command()
@click.argument("bib_key")
def delete(bib_key):
    base.del_entry(bib_key)

@click.command()
def write():
    base.write_bib_file()

cli.add_command(init)
cli.add_command(add)
cli.add_command(delete)
cli.add_command(write)
