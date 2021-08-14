import bibtexparser as btp
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from scholarly import scholarly

import copy
import json
import os
import pyperclip
import re
import requests
import yaml

CFG_FILE_NAME = "bibworm.yml"

DB_PATH = ".bibworm/db.bib"
DBLP_BASE_URL = "https://dblp.uni-trier.de/rec/"
DBLP_API_URL = "https://dblp.org/search/publ/api?q="

syn = {"year" : ["pub_year"]}

def _download_dblp_entry(bib_key):
    responses, success = [], True
    for condensed in [1,0]:
        url = DBLP_BASE_URL + bib_key[5:] + f".bib?param={condensed}"
        response = requests.get(url)
        responses.append(response.content)
        sucess = success and response.status_code == 200
        if not success:
            return _, False

    return responses, True

def _dblp_key_from_title(title):
    url = title.lower()
    url = title.replace(" ", "+")
    url = DBLP_API_URL + url + "&format=json"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    hits = json.loads(response.content.decode("utf-8"))["result"]["hits"]
    if not "hit" in hits:
        return None
    return hits["hit"][0]["info"]["key"]

def _download_gscholar_entry(bib_key):
    try:
        query = scholarly.search_single_pub(bib_key)
    except (Exception, IndexError):
        return None
    return scholarly.bibtex(query)

def _cfg_file_path():
    return os.path.join(os.getcwd(), CFG_FILE_NAME)

def _get_cfg():
    cfg_path = _cfg_file_path()
    if not os.path.isfile(cfg_path):
        print("Error, not configuration file provided")
        return
    with open(cfg_path, "r") as f:
        return yaml.load(f, yaml.SafeLoader)

def _read_db():
    db_path = os.path.join(os.getcwd(), DB_PATH)

    if not os.path.isfile(db_path):
        basedir = os.path.dirname(db_path)
        os.makedirs(basedir, exist_ok=True)
        with open(db_path, "w") as f:
            pass
        return {}

    with open(db_path, "r") as f:
        db = yaml.load(f, yaml.SafeLoader)
        return db if db is not None else {}

def _write_db(db):
    db_path = os.path.join(os.getcwd(), DB_PATH)
    with open(db_path, "w") as f:
        f.write(yaml.dump(db, default_flow_style=False))
    write_bib_file()

def _format_entry(entry):
    for key in entry.keys():
        entry[key] = entry[key].strip()
        entry[key] = entry[key].replace("\n", " ") # do not wrap lines
        entry[key] = re.sub("\s{2,}", " ", entry[key]) # remove multiple spaces after each other
    return entry

def _tidy_entry(entry, cfg):
    etype, eid = entry["ENTRYTYPE"], entry["ID"]
    if not etype in cfg:
        print("Entry type not provided in config file:", etype)
        return None

    def find_synonym(field):
        if not field in syn:
            return None
        for f_syn in syn[field]:
            if f_syn in entry:
                return f_syn
        return None

    t_entry = {}
    for field, option in cfg[etype].items():
        if option == "r":
            if not field in entry:
                f_syn = find_synonym(field)
                if f_syn is None:
                    print(f"Required field '{field}' not provided by entry {eid}")
                    continue
                t_entry[field] = entry[f_syn]
            else:
                t_entry[field] = entry[field]
        elif option == "o":
            if field in entry:
                t_entry[field] = entry[field]

    t_entry = _format_entry(t_entry)
    t_entry.update({"ENTRYTYPE": etype, "ID": eid})
    return t_entry


def write_bib_file():
    db = _read_db()
    cfg = _get_cfg()
    tidy_entries = []

    for bib_key, entry in db.items():
        if bib_key.startswith("DBLP") and "condensed" in entry and cfg["dblp_condensed"] == "y":
            entry = entry["condensed"][bib_key]
        t_entry = _tidy_entry(entry, cfg)
        if t_entry is not None:
            tidy_entries.append(t_entry)

    bib_db = BibDatabase()
    bib_db.entries = tidy_entries
    with open(cfg["bib_file"], "w") as f:
        f.write(BibTexWriter().write(bib_db))

def _first_key(d):
    return list(d.keys())[0]

def _update_db(entry, db):
    cfg = _get_cfg()
    tmp_db = BibDatabase()
    to_tidy = copy.deepcopy(entry)
    bib_key = _first_key(entry)
    if "condensed" in entry[bib_key]:
        del(to_tidy[bib_key]["condensed"])

    to_tidy = to_tidy.popitem()[1]
    tmp_db.entries = [_format_entry(to_tidy)]

    ans = input(f"Add bib entry below?\n{BibTexWriter().write(tmp_db)}[y/n]")
    if ans != "y":
        print("Entry discarded")
        return

    db.update(entry)
    _write_db(db)
    pyperclip.copy(bib_key)

def add_dblp_key(bib_key):
    assert(bib_key.startswith("DBLP"))

    db = _read_db()
    if bib_key in [key for key, _ in db.items()]:
        print("Already stored in the database")
        return

    entries, success = _download_dblp_entry(bib_key)
    if not success:
        print("Failed to download entry")
        return

    entry = btp.loads(entries[0]).entries_dict
    entry[_first_key(entry)]["condensed"] = btp.loads(entries[1]).entries_dict
    _update_db(entry, db)

def add_dblp_title(title):
    bib_key = _dblp_key_from_title(title)
    if bib_key is None:
        print("Nothing found on dblp, searching on Google Scholar...")
        add_google_scholar_title(title)
        return
    add_dblp_key("DBLP:" + bib_key)

def add_google_scholar_title(title):
    db = _read_db()

    entry = _download_gscholar_entry(title)
    if entry is None:
        print("Failed to download entry")
        return

    _update_db(btp.loads(entry).entries_dict, db)

def del_entry(bib_key):

    db = _read_db()

    if not bib_key in db.keys():
        print(f"Bib bib_key {bib_key} not found")
        return

    del(db[bib_key])
    _write_db(db)
