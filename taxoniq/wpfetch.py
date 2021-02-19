#!/usr/bin/env python3
#from concurrent.futures import ThreadPoolExecutor
#with ThreadPoolExecutor() as executor:
#    for res in executor.map(...):

import os
import json
import subprocess

import urllib3
http = urllib3.PoolManager(maxsize=min(32, os.cpu_count() + 4))


def get_taxonbar_page_ids():
    params = dict(action="query", list="embeddedin", eititle="Template:Taxonbar", format="json", eilimit=500)
    while True:
        res = http.request("GET", url="https://en.wikipedia.org/w/api.php", fields=params)
        assert res.status == 200
        page = json.loads(res.data)
        for pageset_start in range(0, len(page["query"]["embeddedin"]), 50):
            yield [str(record["pageid"]) for record in page["query"]["embeddedin"][pageset_start:pageset_start+50]]
        if not page.get("continue"):
            break
        params.update(page["continue"])


def get_wiki_pages(domain="www.wikidata.org", **kwargs):
    params = dict(action="query", prop="revisions", rvprop="content", format="json", **kwargs)
    res = http.request("GET", url=f"https://{domain}/w/api.php", fields=params)
    assert res.status == 200
    res_doc = json.loads(res.data)
    for page in res_doc["query"]["pages"].values():
        assert page["ns"] == 0
        assert len(page["revisions"]) == 1
        #assert page["revisions"][0]["contentformat"] == "text/x-wiki"
        #assert page["revisions"][0]["contentmodel"] == "wikitext"
        yield page["pageid"], page["title"], page["revisions"][0]["*"]


def get_wikidata_linkshere(title):
    params = dict(action="query", prop="linkshere", lhnamespace="0", lhprop="pageid|title", lhlimit=500, format="json", titles=title)
    while True:
        res = http.request("GET", url="https://www.wikidata.org/w/api.php", fields=params)
        assert res.status == 200
        res_doc = json.loads(res.data)
        for page_links in res_doc["query"]["pages"].values():
            for pageset_start in range(0, len(page_links["linkshere"]), 50):
                yield [str(record["pageid"]) for record in page_links["linkshere"][pageset_start:pageset_start+50]]
        if not res_doc.get("continue"):
            break
        params.update(res_doc["continue"])


def get_extracts(titles, domain="en.wikipedia.org"):
    assert len(titles) <= 20
    params = dict(action="query", prop="extracts", exintro=True, exchars=500, format="json", titles="|".join(titles))
    res = http.request("GET", url=f"https://{domain}/w/api.php", fields=params)
    assert res.status == 200
    res_doc = json.loads(res.data)
    for page in res_doc["query"]["pages"].values():
        assert page["ns"] == 0
        yield page


with open("/mnt/wikipedia_extracts.json", "w") as fh:
    i=0
    for pageid_set in get_wikidata_linkshere("Q16521"):
        tax_data_by_title = {}
        for pageid, title, page in get_wiki_pages(pageids="|".join(pageid_set)):
            page = json.loads(page)
            name, claims = page["labels"]["en"]["value"], page["claims"]
            if "enwiki" not in page["sitelinks"]:
                continue
            en_wiki_title = page["sitelinks"]["enwiki"]["title"]
            if "P31" not in claims or "P685" not in claims:
                continue
            if claims["P31"][0]["mainsnak"]["datavalue"]["value"]["id"] != "Q16521":
                continue
            taxid = claims["P685"][0]["mainsnak"]["datavalue"]["value"]
            tax_data_by_title[en_wiki_title] = dict(taxid=taxid, wikidata_id=title, en_wiki_title=en_wiki_title)

        titles = list(tax_data_by_title.keys())
        for titleset_start in range(0, len(titles), 20):
            for extract in get_extracts(titles[titleset_start:titleset_start+20]):
                tax_data_by_title[extract["title"]]["extract"] = extract["extract"]
        '''
        #api.php?action=query&prop=extracts&exchars=175&titles=Therion
        for pageid, title, page in get_wiki_pages(domain="en.wikipedia.org", titles="|".join(tax_data_by_title)):
            try:
                plain_page = subprocess.check_output(["pandoc", "-f", "mediawiki", "-t", "plain"], input=page.encode()).decode()
                plain_page = plain_page[:plain_page.find("\n\n")]
            except subprocess.CalledProcessError:
                plain_page = ""
            print(title)
            print(plain_page)
            print("---")
            #print(pageid, title, name, tax_id, en_wiki_title)
            #    if line.startswith("{{Taxonbar|"):
            #        print(pageid, title, line)
        '''
        for tax_datum in tax_data_by_title.values():
            fh.write(json.dumps(tax_datum) + "\n")
            i+=1
        print(i)

#for tax_id in tax_data:
#    print(tax_id, "\t", tax_data[tax_id])
