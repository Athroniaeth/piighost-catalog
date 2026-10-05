# The site

A Svelte application served by nginx, talking to the API under `/api/v1` from a
single origin. Eight routes, no server-side state, no accounts.

| Route | What you do there |
|---|---|
| `/` | the catalogue: search, sort, object list, tickable facets |
| `/r/:ns/:name[/:selector]` | one object: commit history on the left, the Content, Pipeline file and Use it tabs on the right |
| `/playground` | run an object or a candidate regex over a text |
| `/playground/compare` | two to four objects over the same text |
| `/playground/chat` | the whole round trip, with a scripted assistant |
| `/contribute` | write a pattern or a group in two columns, try it and check it from the foot of the second |
| `/labels` | every label the registry can emit, from the footer |
| `/stats` | how the registry is used, from counters aggregated to the hour |

## Structure, after the LangSmith Hub

The layout follows the [LangSmith Hub](https://smith.langchain.com/hub), which
distributes prompts as this site distributes configurations, and whose gestures
`piighost`'s visitors already know.

- **A breadcrumb bar, not a navbar.** The mark, then the page's place in the
  registry, `piighost / fr-default`. On the right, the two things a visitor
  does, the playground and contributing, then GitHub, the theme and the
  language.
- **A centred title and a pill search.** The home page is the catalogue: a
  title, one line, a wide search field, and the list immediately.
- **Sort chips.** Widest coverage, relevance, recently updated, most used, name.
  With no query the default is coverage: someone arriving without typing
  anything is looking for what covers the most, not for what a maintainer
  touched last. As soon as a query is typed, relevance takes over.
- **A vertical list, not a grid.** Each row leads with its pills (the kind, then
  the tags), the reference as the title, the description over two lines, then a
  metadata line: update date, number of labels, of commits and of uses. A "Try
  it" button on the right opens the playground with the object loaded.
- **Tickable facets with counts**, in a column on the right, grouped by family:
  type, region, category, domain, use case, language. The families come from the
  vocabulary's `kind`; manifest authors never see them.
- **A two column object page.** On the left, the commit history, each card
  carrying its hash, its pointer tags and its date. On the right, the shown
  commit with its pointers, then tabs: Content, Pipeline file, Use it. The title
  bar carries the reference, the pills and three actions: copy the reference,
  download, try it.

## The charter

The site takes `piighost-studio`'s charter so the ecosystem reads as one thing:
shadcn's neutral scale, a single violet primary, Geist for text and Geist Mono
for code and the wordmark, a 0.625rem base radius. Light is the default and dark
is a class on `<html>` set by the visitor, never inferred from the system, as the
studio does. The mark is piighost's placeholder reduced to a glyph, two chevrons
and the bar where the value used to be, defined once in `Wordmark`, which the
title, the breadcrumb and the footer share.

Fonts are self-hosted through `@fontsource-variable/geist`, the CSP allowing no
other origin. Icons come from lucide, one per import.

**Three surfaces, one grammar.** The playground, the comparison, the chat and the
contribution page are the same card in three numbered columns, Configure, Text,
Results, with an identical region header. The `Region` component carries that
grammar and the four pages import it.

**Contributing is a form.** A pattern, a group and a configuration each have
one; the configuration falls back to the TOML editor when it holds what the form
cannot write back, a detector with a model or a stage outside the three standard
ones, naming the piece in the way. Every example of a pattern carries its verdict
live, answered by the Python engine that will run it, because a browser cannot
answer that question honestly.

**A configuration is not contributed here.** A pattern and a group each have
their form; a configuration had one too, complete and tested, and it was taken
out. Assembling detectors and pipeline stages is a larger interface than a form,
and the intended path goes through a conversation rather than a grid of pickers.
The form that existed is kept at the git tag `config-form/v1`, whose message
lists the files to restore. The API still accepts a `config` submission.


**Entity colours are the studio's.** A palette of fifteen hues handed out by
first appearance, `PERSON` on the primary, carried verbatim from `labels.ts`. A
label therefore keeps the same colour in the catalog and in the studio's playground.

**The components.** Under `components/ui/`: `Button`, `Badge`, `Card`,
`Segmented`, `Tabs`, `Region`, `StepChip`, `CodeBlock`, `CopyButton`. Above
them: `EntityLabel`, `EntityRow`, `EntityHighlight`, `ObjectCard`, `RefPicker`,
`SamplePicker`, `SiteNav`, `SiteFooter`. Native controls share their classes
from `lib/ui.ts` rather than a component per field.

## Choices that show

**Filters live in the URL.** A filtered view has to be shareable, and the back
button has to undo a filter rather than leave the page. The catalogue therefore
reads `q`, `kind`, `tag` (repeatable) and `label` from the query string, and has
no state of its own.

**Two languages, down to the manifests.** The registry is bilingual by
construction, every description carrying `en` and `fr`. The language switch also
writes `document.documentElement.lang`, which is where a screen reader takes its
voice from.

**Two columns, and two dialogs.** The page carried three: identity, content,
findings. The third earned its place at two moments only, reading the outcome of
a check and trying a group, and crowded the other two the rest of the time. What
is still missing shows at the foot of the second column, above the buttons; the
outcome of a check and the try panel are native `<dialog>` elements. The top
layer also avoids the clipping the card imposes on anything that overflows,
learned twice on this project.

**A group can be tried without being published, and without sending the text.**
The "Run here" button flattens the sources through the API, because deciding
what happens when two sources carry one label is the registry's rule and there
must be one implementation of it. Then it runs the result with piighost itself,
compiled to WebAssembly by Pyodide, in the tab. The catalogue is public; the text
is not, and it goes nowhere.

That is what justifies the CSP's one concession, `wasm-unsafe-eval` in
`script-src`. The name is alarming and the scope is not: it permits compiling
WebAssembly, not `eval`, not `new Function`, not inline script. Pyodide and the
wheel are served from this origin, never from a CDN and never from PyPI, so
`connect-src 'self'` does not move either.

**No inline styles.** The production CSP allows `style-src 'self'` with no
`unsafe-inline`. Syntax highlighting that emitted `style="color:…"` would work in
development and break in production, so highlighting goes through classes and the
colours live in the stylesheet. The built bundle holds no `style` attribute.

**A printable page.** The `no-print` class removes the controls and the sheet
turns black on white. A data protection officer reads a coverage sheet on paper,
not a TOML file.

**A router in one file.** Eight routes, no nested layouts: a routing dependency
would cost more in indirection than it gives. nginx already serves `index.html`
as a fallback, which is all a history router needs. Links stay real `<a href>`,
so middle-click and open-in-a-tab work.

## What the playground does not do

Model detectors, GLiNER2 and spaCy, do not run: weights would have to be
downloaded and loaded on every request. A configuration carrying one is still
runnable, its regex detectors run, and the response names what was skipped in
`unsupported`. The object page says so too.

Running a model in the browser through Pyodide, as `piighost`'s own presentation
site does, remains the right answer eventually: the text would not leave the
machine, which is exactly the argument for a PII tool. That is an application in
its own right, not a checkbox here.
