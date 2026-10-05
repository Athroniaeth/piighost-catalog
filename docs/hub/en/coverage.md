# Coverage

What this registry measures itself against, and what the measurement does not
say.

A pattern registry written by its authors ends up covering what its authors know.
This page compares its labels against inventories published by people with
different blind spots, and keeps the comparison reproducible:

```bash
python3 scripts/coverage_report.py          # HUB_INVENTORIES points at the inventory directory
```

## The sources

| Source | Types | What it is |
|---|---|---|
| Microsoft Purview | 325 | the sensitive information types of the Microsoft 365 suite |
| Google Cloud DLP | 261 | the infoTypes of Sensitive Data Protection, including a long per-country series |
| Nightfall | 179 | a commercial DLP service, public catalog |
| AWS Macie | 167 | the managed data identifiers, plus Comprehend's PII types |
| Cloudflare DLP | 143 | the predefined profiles, including entries aimed at AI prompts |
| Microsoft Presidio | ~50 | the predefined recognisers, the only inventory whose code can be read |
| AI4Privacy | 56 and 20 | the label sets of two de-identification training corpora |

The first four are commercial catalogs: their existence proves a customer paid
for those shapes, which is a signal of real frequency. Presidio is the only one
whose regex can be read, and therefore judged. AI4Privacy gives corpus labels,
not patterns.

## What the comparison says

Matching is done on a (country, concept) pair rather than on a name, since the
same thing is called `FRANCE_CNI`, `FR_CNI` or `France identity card` depending
on the vendor.

A single number survives interpretation badly, so here is what to take from it
instead of a percentage:

- **The driving licence is the best evidenced gap.** All five sources carry it,
  for a dozen countries. It is the first thing to write.
- **The BIC/SWIFT code** appears in five sources and was missing here, although
  its shape is clean and unambiguous.
- **The most cited countries the registry ignores** are Japan, Ireland, Korea,
  Indonesia, Austria, Finland and Portugal.
- **The passport** is carried everywhere, country by country, and the registry
  had exactly one, the American.

## What the comparison does not say

A good part of what these catalogs call PII has no shape at all. A name, an
age, a postal address written out, an ethnic origin, a political opinion, a
diagnosis: no regex finds those, and pretending otherwise produces a pattern
that flags everything. Those categories are the business of the NER or LLM
detector, which `piighost` plugs in beside the regex detector, not of this
registry.

Another part depends on context keywords or on a checksum, which this registry
refuses on principle, since a value mangled by OCR has to stay detected rather
than rejected. A vendor advertising a thousand types is therefore counting
something other than what is counted here.

Finally, coverage is not quality. Two patterns for one country are worth more
than six fighting over the same span, and the registry's composition check
refuses publication in that case, which none of these catalogs does.

## How to use it

The report ranks the gaps by how many independent sources carry them. A gap
cited by four vendors out of five deserves to be written; one cited by a single
vendor deserves a question: is this a real shape, or that catalog's speciality?
