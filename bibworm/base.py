import bibtexparser as btp
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from scholarly import scholarly

import json
import os
import re
import requests
import yaml

CFG_FILE_NAME = "bibworm.yml"

DB_PATH = ".bibworm/db.bib"
DBLP_BASE_URL = "https://dblp.uni-trier.de/rec/"
DBLP_API_URL = "https://dblp.org/search/publ/api?q="

syn = {"year" : ["pub_year"]}

def _download_dblp_entry(bib_key):
    url = DBLP_BASE_URL + bib_key[5:] + ".bib?param=1"
    response = requests.get(url)
    return response.content, response.status_code == 200

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

def _tidy_entry(entry, cfg):
    etype, eid = entry['ENTRYTYPE'], entry['ID']
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
                    return None
                t_entry[field] = entry[f_syn]
            else:
                t_entry[field] = entry[field]
        elif option == "o":
            if field in entry:
                t_entry[field] = entry[field]

    for key in t_entry.keys():
        t_entry[key] = t_entry[key].strip()
        t_entry[key] = t_entry[key].replace("\n", " ") # do not wrap lines
        t_entry[key] = re.sub("\s{2,}", " ", t_entry[key]) # remove multiple spaces after each other

    t_entry.update({"ENTRYTYPE": etype, "ID": eid})
    return t_entry


def write_bib_file():
    db = _read_db()
    cfg = _get_cfg()
    tidy_entries = []

    for bib_key, entry in db.items():
        t_entry = _tidy_entry(entry, cfg)
        if t_entry is not None:
            tidy_entries.append(t_entry)

    bib_db = BibDatabase()
    bib_db.entries = tidy_entries
    with open(cfg["bib_file"], "w") as f:
        f.write(BibTexWriter().write(bib_db))

def _update_db(new_entry, db):
    fetched_db = btp.loads(new_entry)
    assert(len(fetched_db.entries) == 1)
    new_entry = fetched_db.entries_dict
    tmp_db = BibDatabase()
    tmp_db.entries = [_tidy_entry(fetched_db.entries[0], _get_cfg())]
    ans = input(f"Add bib entry below?\n{BibTexWriter().write(tmp_db)}[yN]")
    if ans != "y":
        print("Entry discarded")
        return
    db.update(new_entry)
    _write_db(db)

def add_dblp_key(bib_key):
    assert(bib_key.startswith("DBLP"))

    db = _read_db()
    if bib_key in [key for key, _ in db.items()]:
        print("Already stored in the database")
        return

    entry, success = _download_dblp_entry(bib_key)
    if not success:
        print("Failed to download entry")
        return

    _update_db(entry, db)

def add_dblp_title(title):
    bib_key = _dblp_key_from_title(title)
    if bib_key is None:
        print("No publication found")
        return
    add_dblp_key("DBLP:" + bib_key)

def add_google_scholar_title(title):
    db = _read_db()

    entry = _download_gscholar_entry(title)
    if entry is None:
        print("Failed to download entry")
        return

    _update_db(entry, db)

def del_entry(bib_key):

    db = _read_db()

    if not bib_key in db.keys():
        print(f"Bib bib_key {bib_key} not found")
        return

    del(db[bib_key])
    _write_db(db)
