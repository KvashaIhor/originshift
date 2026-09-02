# Security

## Reporting a vulnerability

Use GitHub's [private vulnerability reporting][pvr] on this repository. It opens
a channel only you and I can read, and it does not create a public issue.

[pvr]: https://github.com/KvashaIhor/originshift/security/advisories/new

**What to expect.** One maintainer, no embargo process, and no service-level
agreement. I will acknowledge a report within five business days and tell you
what I intend to do about it. If a fix warrants one, the advisory is published
with the release that carries it.

## What is in scope

The package runs in your process. It reads its corpus from disk, keeps no state
between calls, and makes no network request while resolving. That leaves a small
surface, and these are the parts of it worth reporting:

- Anything that executes code from a corpus, an overlay, or a CSV
- A path in `ingest`, `sources` or `build_corpus` that writes outside the cache
  and data directories it is supposed to write to
- A crafted overlay or corpus that makes the resolver return an origin without
  the provenance that says where the rule came from

Fetching sources and rebuilding the corpus **do** make network requests, to the
eCFR and to CBP. Both are separate commands you run deliberately, and both go to
government endpoints over HTTPS with `certifi`'s trust store, because the Python
builds this package targets ship no usable one of their own.

## What is not a vulnerability

**A wrong determination is a correctness bug.** Open an ordinary issue for it.
The corpus is scored against CBP's own rulings and every disagreement is
published, so a defect belongs in the open where it stays visible while it is
being resolved.

**A defect in the regulation is neither of those.** 19 CFR 102.20 contains transcription
errors and 102.21 has an entry the Federal Register published and the CFR never
incorporated. Those ship reported, in the corpus `anomalies` list, with the
verbatim text. They are not repaired here, because repairing them would put
words in the regulation's mouth.

## Supply chain

Releases are published from GitHub Actions through PyPI Trusted Publishing. No
API token exists to steal. Each artefact carries a [PEP 740][pep740]
attestation binding it to this repository and to `release.yml`, which you can
check without trusting me:

```
curl -s https://pypi.org/integrity/originshift/<version>/<filename>/provenance
```

The attestation binds a repository and a workflow. It does not attest a person.

[pep740]: https://peps.python.org/pep-0740/

One runtime dependency, `certifi`. Dependabot alerts and security updates are
enabled.
