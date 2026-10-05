# Making the registry findable

A companion to the project-wide visibility plan, which audits the library and
its documentation site. This one is about `catalog.piighost.dev`, which that plan
does not mention and which is a different problem: the library has one page,
the registry has 226.

## What changed, and why it had to change first

Until September 2026 every URL on the catalog served the same 1.3 KB document:
the product name (then `piighost hub`) as its title, nothing in its body, the
whole registry behind a bundle. Google renders JavaScript, eventually and within
a budget. The crawlers that feed the assistants people now ask _how do I redact
PII before a prompt_ mostly do not.

That was the mechanical reason the catalog could not be cited, and no directory
submission would have changed it. It is fixed: `scripts/prerender.mjs` writes
one real HTML file per route at build time, each with its own title,
description, canonical, `og:url` and schema.org JSON-LD, and with the content
in the document rather than behind the bundle. `/llms.txt` is generated from
the registry beside `robots.txt` and `sitemap.xml`.

Everything below assumes that baseline.

## The three things worth doing next

### 1. The registry is the long tail, and the library is not

Nobody searches for `piighost`. People search for the thing they are stuck on:

| They type                                    | The page that answers it           |
| -------------------------------------------- | ---------------------------------- |
| `regex numéro sécurité sociale française`    | `/r/piighost/fr-nir`               |
| `SIRET regex validation`                     | `/r/piighost/fr-siret`             |
| `detect AWS access key in logs regex`        | `/r/piighost/aws-access-key`       |
| `UK national insurance number regex`         | `/r/piighost/uk-nino`              |
| `redact database connection string password` | `/r/piighost/db-connection-string` |

The registry covers 56 government identifiers, 44 contact shapes, 25 credential
shapes and 28 countries. Each is a page that already exists, now indexable, and
each answers a question that gets asked in isolation — which is exactly the
traffic a library landing page never captures.

What this needs is not more pages. It needs the existing ones to say, in their
first sentence, what shape they match and for which country, because that
sentence is the meta description. Auditing the 226 descriptions against that
test is the highest-yield content work available.

### 2. The two sites do not link to each other

`piighost.dev` and `catalog.piighost.dev` are two domains with no mesh between
them. Free signal, currently unspent:

- Every object page should link to the library's detector reference.
- The library's `reference/detectors.md` should link to the catalog for
  browsing, not only for `from_catalog`.
- `piighost.dev` should carry the catalog in its navigation, not only in prose.

### 3. Google Dataset Search is empty in this field

Every object is now marked up as a schema.org `Dataset`, the registry as a
`DataCatalog`. That is not a costume: an object is a versioned, addressable set
of records with a licence and a provenance. Dataset Search indexes that
vocabulary, it ranks on queries no software directory competes for, and nothing
in PII de-identification is currently there.

Submit `catalog.piighost.dev` to Google Search Console and Bing Webmaster Tools,
then check the Dataset report. This is the one channel where being early is
worth more than being good.

## Submission targets specific to a regex registry

The project-wide plan lists the library's targets. These are the registry's,
and they are different: a catalogue of tested patterns belongs in places a
Python package does not.

- [ ] **regex101 / regexr community libraries** — each pattern is a candidate,
      with a link back. Submit a handful of the best, not 226.
- [ ] **Awesome Regex** (`aloisdg/awesome-regex`) — under resources.
- [ ] **OWASP Validation Regex Repository** — the reference list for exactly
      this, and stale. Contributing there is contributing to the field.
- [ ] **Google Dataset Search**, via Search Console.
- [ ] **Hugging Face Datasets** — the registry exports as JSON; a dataset card
      pointing back to the catalog indexes very well and costs one upload.
- [ ] **Data Privacy Stack** (`microsoft.github.io/presidio/community`) — the
      library belongs there; so does the registry, as a pattern source.

One pull request per target, in that project's format, as the project-wide plan
requires. Track them in `docs/growth/submissions.md`.

## What not to do

The rules from the project-wide plan apply here without exception. Two are
worth restating because a registry invites breaking them:

- **Do not generate pages to rank.** A pattern earns a page by passing the
  checks, not by matching a query. A registry padded with untested patterns is
  worth less than one with 226 that hold.
- **Do not claim detection rates.** The registry guarantees that examples are
  replayed, that composition holds and that backtracking is bounded. It
  guarantees nothing about recall on your text, and every page should keep
  being honest about that.

## Measuring

The catalog already reports to OpenPanel, and `/stats` shows pulls and searches.
What is missing is the outside view:

- Impressions and position per page, from Search Console, weekly.
- Whether an assistant names the catalog when asked where to find a tested regex
  for a French social security number. Quarterly, same questions each time.
- Referring domains, which is the metric the submissions above move.

The second one is the metric that motivated all of this, and the only one that
cannot be gamed.
