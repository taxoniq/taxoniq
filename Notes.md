- see if https://www.niaid.nih.gov/research/emerging-infectious-diseases-pathogens should be integrated

- build matrix: build wheels for python 3.5-3.9 for linux-amd64, macos, windows, linux-arm (?), deposit build artifacts
- release gh action: upload build artifacts to pypi


# Cookbook

* Given a taxon ID, retrieve its full or ranked lineage:

```
- Taxon.pubmed_ids
- given a taxon, produce a full lineage (list of all taxa from the root of the tree to this taxon)
- given a taxon, produce a lineage only at standard ranks
- given a taxon, produce a lineage only at specified ranks
- given a taxon list, produce an LCA taxon
- given two taxa, produce a total evolutionary distance between them
- given two taxa, produce a path with evolutionary distances

- given an accession ID, produce an offset in NCBI nt/nr
  - Q: how to indicate version of ncbi nr/nt that the offset is valid in?

- check wikipedia dump loader
  - load all structured info in wikipedia articles as k/v
  - full-text queries on wikipedia descriptions

- check taxize API https://docs.ropensci.org/taxize/reference/index.html
- check onecodex and ETE for other relevant features

- represent all cross-linked information from https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?mode=Info&id=7955&lvl=3&srchmode=1&keep=1&unlock
- query traversal on tree
```

# Links and prior art

https://github.com/onecodex/taxonomy
http://etetoolkit.org/
https://github.com/HadrienG/taxadb
https://github.com/ropensci/taxize

Taxon identifiers
Wikidata: Q154625
Wikispecies: Neisseria meningitidis
BacDive: 10473EoL: 996566
GBIF: 3220226i
Naturalist: 570710
IRMNG: 10528686ITIS: 964013
LPSN: neisseria.html#meningitidis
NCBI: 487
NZOR: baa82ec7-2df2-4565-8e7b-4419602fd533




    
#print(int.from_bytes(trie["NM_174292"][0], sys.byteorder))

'''

    for proc in dl_procs:
        if proc.wait() != os.EX_OK:
            raise Exception(f"{proc} failed")

    accessions_in_nt = set()
    i=0
    with gzip.open("nt_fasta_headers.gz", mode="rt") as nt_fh:
        for fasta_line in nt_fh:
            accession = fasta_line.split()[0].lstrip(">")
            accessions_in_nt.add(accession)
            i+=1
            if i % 1000000 == 0:
                print("acc_in_nt", i)

    sql = f"CREATE TABLE accession2taxid (accession_version text primary key, tax_id integer) WITHOUT ROWID" # TODO: foreign key
    sql = f"CREATE TABLE accession2taxid (tax_id integer)" # TODO: foreign key
    conn.execute(sql)
    sql = "INSERT INTO accession2taxid VALUES (:accession_version, :tax_id)"
    sql = "INSERT INTO accession2taxid VALUES (:tax_id)"
    with gzip.open("nucl_gb.accession2taxid.gz", mode="rt") as a2t_fh:
        a2t_fh.readline()
        i, j = 0, 0
        for line in a2t_fh:
            accession, accession_version, tax_id, gi = line.split()
            if accession_version in accessions_in_nt:
                if accession_version.endswith(".1"):
                    accession_version = accession_version[:-len(".1")]
#                conn.execute(sql, dict(accession_version=accession_version, tax_id=int(tax_id)))
                conn.execute(sql, dict(tax_id=int(tax_id)))
                j+=1
            i+=1
            if i % 1000000 == 0:
                print("a2t", i, j, j/i)
'''

# WITHOUT ROWID: https://sqlite.org/withoutrowid.html
# FIXME: to shrink a2t, replace text primary key with integer row id; use suffix tree to store accession string->row id mapping
# Q: can this be achieved within sqlite?

# FIXME: vacuum here

#    accession       accession.version       taxid   gi
#    conn.executemany('INSERT INTO host VALUES (?,?)', HostReader())


"""
    conn.execute('CREATE VIRTUAL TABLE posts USING FTS5(title, body);')
    conn.execute('''INSERT INTO posts(title,body)
VALUES('Learn SQlite FTS5','This tutorial teaches you how to perform full-text search in SQLite using FTS5'),
('Advanced SQlite Full-text Search','Show you some advanced techniques in SQLite full-text searching'),
('SQLite Tutorial','Help you learn SQLite quickly and effectively');''')
    conn.execute('''SELECT * 
FROM posts 
WHERE posts MATCH 'fts5';''')

#print(c.fetchone())
"""

TODO: check if https://ftp.ncbi.nlm.nih.gov/genomes/Viruses/all.fna.tar.gz needs to be fetched
