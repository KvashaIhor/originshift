"""Look for anyone citing or depending on the work, and print what turns up.

Run it whenever you want a picture; it queries public APIs only and stores
nothing. Downloads say how many, never who — these say who.
"""

import json
import ssl
import urllib.request
import urllib.parse

import certifi

# python.org builds ship no usable trust store, which is why the package
# depends on certifi at all. The same applies here.
_CTX = ssl.create_default_context(cafile=certifi.where())

CONCEPT_DOI = "10.5281/zenodo.22181363"
REPO = "KvashaIhor/originshift"
UA = {"User-Agent": "originshift-citation-check (+https://github.com/%s)" % REPO}


def get(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30, context=_CTX) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_error": str(e)}


def section(title):
    print("\n" + title)
    print("-" * len(title))


section("DataCite — works citing or referencing the DOI")
q = urllib.parse.quote(f'relatedIdentifiers.relatedIdentifier:"{CONCEPT_DOI}"')
d = get(f"https://api.datacite.org/dois?query={q}&page[size]=25")
hits = d.get("data", []) if "_error" not in d else []
print(f"  {len(hits)} found" + (f"  ({d['_error']})" if "_error" in d else ""))
for h in hits:
    a = h.get("attributes", {})
    print("   ", a.get("doi"), "|", (a.get("titles") or [{}])[0].get("title", "")[:70])

section("OpenAIRE — linked research products")
d = get(f"https://api.openaire.eu/search/researchProducts?doi={CONCEPT_DOI}&format=json")
print("  raw response keys:", list(d)[:5] if isinstance(d, dict) else type(d))

section("Zenodo — versions and their download counts")
d = get(f"https://zenodo.org/api/records?q=conceptdoi:%22{CONCEPT_DOI}%22&all_versions=true")
for h in d.get("hits", {}).get("hits", []) if "_error" not in d else []:
    s = h.get("stats", {})
    print(f"   {h.get('doi')}  downloads={s.get('downloads')}  views={s.get('views')}")

section("GitHub — repositories whose code mentions originshift")
print("  needs a token; run:")
print("    gh api -X GET search/code -f q='originshift language:Python -repo:%s' \\" % REPO)
print("      --jq '.items[].repository.full_name' | sort -u")

section("GitHub — forks, stargazers, dependents")
print("    gh api repos/%s/stargazers --jq '.[].login'" % REPO)
print("    gh api repos/%s/forks --jq '.[].owner.login'" % REPO)
print("    open https://github.com/%s/network/dependents" % REPO)

section("Set these up once, by hand")
print("  Google Scholar alert : scholar.google.com -> search 'originshift' -> Create alert")
print("  Google/Bing alerts   : \"originshift\", \"19 CFR 102.21\" corpus")
print("  PyPI download counts : https://pepy.tech/project/originshift  (scale, never identity)")
