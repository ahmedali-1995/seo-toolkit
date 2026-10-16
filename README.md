# seo-toolkit

Six small SEO engineering tools written as a developer would write them: plain Python 3.10+, **zero runtime dependencies**, typed, tested, and runnable offline against the sample data in `data/`.

SEO work is mostly data processing and HTML/HTTP parsing, which makes it a good fit for code you can diff, test and run in CI instead of spreadsheets and one-off exports.

```bash
python -m unittest discover -s tests      # 22 tests, ~0.5 s, no network
python -m seo_toolkit <command> ...       # see "Tools" below
```

## Live demo

A small web UI (`public/`) calls the same Python modules through a single stdlib WSGI app (`app.py`, routes in `demo_api/`): FAQ schema builder, JSON-LD validator, keyword clustering, Search Console reports and content-decay detection. The crawler and log analyzer are CLI-only on purpose: a public "enter any URL" crawler is an SSRF risk, and server logs shouldn't be uploaded to a demo.

```bash
python scripts/dev_server.py 8000    # local preview, stdlib only
```

Demo hardening: 300 KB request cap, row and keyword limits, no stored input, no tracebacks returned to the client, and the UI renders user content with `textContent` only.

## Tools

| Command | Module | What it does |
|---|---|---|
| `gsc` | `gsc_analyzer` | Striking-distance queries, CTR underperformers, cannibalization, from a Search Console export or the API |
| `crawl` | `crawler` | Polite concurrent crawler; audits titles, descriptions, canonicals, h1s, redirect chains, status codes |
| `cluster` | `clustering` | Groups keywords with TF-IDF + cosine similarity and labels search intent |
| `logs` | `log_analyzer` | Bot crawl analysis from access logs: waste, parameters, status mix, AI crawlers |
| `decay` | `content_decay` | Finds pages losing organic clicks, combining window comparison and a trend fit |
| `faq`, `schema-check` | `schema/` | Builds and validates linked JSON-LD graphs, with a full FAQ pipeline |

```bash
python -m seo_toolkit gsc data/sample_gsc.csv --report striking
python -m seo_toolkit decay data/sample_traffic.csv
python -m seo_toolkit logs data/sample_access.log --bot Googlebot
python -m seo_toolkit cluster data/sample_keywords.txt
python -m seo_toolkit crawl https://example.com --max-pages 50
python -m seo_toolkit faq --category technical --url https://example.com/faq --html
python -m seo_toolkit schema-check data/sample_page.html   # exit code 1 on errors, CI-friendly
```

## Schema and FAQ

The part I spent the most time on, because most structured data on the web is copy-pasted snippets that nobody validates.

**Entity graph, not snippets.** `schema/builders.py` gives every node a stable `@id` (`<url>#organization`, `#webpage`, `#faq`, ...) and combines them with `graph()`. Nodes reference each other by `@id`, so the Organization is defined once and the Article, WebSite and WebPage point to it.

**FAQ pipeline** (`schema/faq.py`):
- Input as JSON or Markdown (`## Question` + answer body), or use the built-in bank of 27 general SEO questions in `data/faq_bank.json`, grouped by category (basics, crawling, technical, content, links, schema, measurement).
- Answers are sanitized to the HTML subset Google documents for FAQ answers (`p, a, ul, ol, li, strong, em, br, h1-h6, div`). Scripts, iframes and event handlers are stripped and `href` is restricted to http(s) and relative URLs.
- Linting before output: duplicate questions, missing `?`, answers too short or too long, promotional wording.
- `render_visible_html()` emits matching on-page markup, because marked-up content must be visible to users.

**Validator** (`schema/validator.py`) extracts every `application/ld+json` block and checks:
1. the JSON parses (errors include line numbers);
2. required properties per type (Article needs headline/author/datePublished, Product needs offers, and so on);
3. every `{"@id": ...}` reference resolves to a node defined on the page;
4. **content parity**: each FAQ question in the markup appears in the visible text of the page. This is the most common FAQ policy violation and few validators check it.

> **Heads-up on FAQ rich results:** since August 2023 Google shows FAQ rich results only for well-known government and health sites. FAQPage markup is still valid and still helps machines understand the page, but don't expect the expandable snippet. The FAQ bank says the same thing, since a toolkit shouldn't promise what the SERP no longer delivers.

## Design notes

- **Stdlib only.** `html.parser`, `urllib`, `concurrent.futures`, `csv`, `argparse`. Installing nothing means it runs in any CI image and is easy to audit. The only optional dependency is Google's client library for the Search Console API.
- **Crawler follows redirects manually** (`_NoRedirect` handler) so the full chain is recorded; `urllib`'s default would hide it. It honours `robots.txt`, caps response size, and has a hop limit that reports loops.
- **Clustering never merges across intent.** "buy running shoes" and "how to choose running shoes" are lexically close but need different pages, so intent is a hard partition and similarity is only compared inside it. The greedy single-pass algorithm is O(n·k); for semantic grouping on huge lists, replace `vectorise()` with an embedding model and keep the rest.
- **Decay detection uses two signals.** A window-over-window drop alone is fooled by a one-time spike in the baseline, so a page is flagged only if the drop passes a threshold *and* the least-squares trend is negative.
- **CTR benchmarks are an assumption.** `EXPECTED_CTR` is an industry-average curve; it is a module constant so it can be replaced with your own site's data.
- **Log analysis** classifies Googlebot, Bingbot, GPTBot, ClaudeBot and others by user agent. User agents can be spoofed, so `verify_googlebot()` implements Google's documented reverse-DNS + forward-confirm check for when it matters.

## Layout

```
seo_toolkit/
  gsc_analyzer.py  crawler.py  clustering.py  log_analyzer.py  content_decay.py
  schema/          builders.py  faq.py  validator.py
  cli.py
app.py            WSGI entrypoint (what Vercel runs) + demo_api/ (route handlers)
public/            demo UI (single static page, no build step)
scripts/           local dev server
data/              sample inputs + faq_bank.json (all synthetic)
tests/             unittest suite, including a local HTTP server for the crawler
```

All sample data is synthetic. Nothing in this repository comes from a real site or employer.

## Limitations

- The crawler doesn't execute JavaScript; it audits the HTML a bot receives first.
- Intent labelling is rule-based and English-only.
- Required-property checks cover common types, not the whole schema.org vocabulary, and are not a replacement for Google's Rich Results Test.

MIT licensed.
