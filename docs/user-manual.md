# User Manual

This manual explains how to use Aithena as a reader or library user. For setup, deployment, and service troubleshooting, see the [Admin Manual](admin-manual.md). For a release-focused summary, see the [v0.4.0 Feature Guide](features/v0.4.0.md).

## Getting started

Aithena is a web app for searching an indexed PDF library. It helps you:

- search by keyword
- narrow results with facets
- open PDFs directly from search results
- check system health in the Status tab
- view library-wide statistics in the Stats tab

### How to access it

Most users will open Aithena through the main web address provided by their administrator.

In a local Docker Compose setup, the main entry point is usually:

- `http://localhost/`

If you are running the frontend in Vite development mode instead of the full stack, the UI may also be available on:

- `http://localhost:5173`

## Searching for books

The **Search** tab is the main place to work.

### Run a search

1. Open **Search**.
2. Enter one or more keywords.
3. Click **Search**.

### What your keywords can match

The current search implementation is built to match against indexed book data, including:

- title
- author
- full PDF text

This makes Aithena useful both for known-item searches such as an author or title and for text discovery inside the book content.

### Understand the results list

Each result card may show:

- title
- author
- year
- category
- language
- page count
- matching text snippets
- file path

If the search engine knows which pages matched, the result also shows a page label such as:

- **Found on page 12**
- **Found on pages 12–14**

### Sort and paging controls

After you search, you can change:

- **Sort**: relevance, year, title, or author
- **Per page**: 10, 20, or 50 results
- **Pagination**: move between result pages with the controls at the bottom

## Using facets to filter results

Facet filters appear in the left sidebar.

### Available facets

You can filter by:

- **Language**
- **Author**
- **Year**
- **Category**

### How to use them

- Click a facet value to apply it.
- Combine values across different facet groups.
- Review active filters above the search results.
- Remove a single filter from its chip.
- Use **Clear all** when multiple filters are active.

### What to expect

- Counts next to each facet show how many matching books are in that bucket.
- Changing a filter refreshes the results immediately.
- When you change a filter, the result list returns to page 1.

## Viewing PDFs

When a result includes an attached document link, you can open the PDF directly from the result card.

### Open a PDF

1. Run a search.
2. Find the result you want.
3. Click **📄 Open PDF**.

The document opens in an overlay viewer without leaving the search page.

### Page navigation from search results

If the search result includes matched page information, Aithena opens the PDF on the first matching page automatically. This is useful when you searched for a term that appears deep inside a long document.

### Close the viewer

You can close the PDF overlay by:

- clicking the **✕** button
- pressing **Escape** on your keyboard

### If a PDF does not load

If the embedded viewer cannot display the file, Aithena shows a fallback link so you can try opening the PDF in a new browser tab.

## Understanding the Status tab

The **Status** tab is a quick health dashboard.

### Indexing Progress

This section shows:

- **Discovered** — books found by the scanner
- **Indexed** — books processed successfully
- **Failed** — books that did not index successfully
- **Pending** — books still waiting or still being processed

### Service Health

This section shows whether key services are reachable:

- **Solr** — search engine health, node count, and indexed document count
- **Redis** — indexing state store
- **RabbitMQ** — queue service used by the ingestion pipeline

### Auto-refresh

The Status tab refreshes automatically every **10 seconds**, so it is the best place to watch the system during imports or after operational changes.

## Understanding the Stats tab

The **Stats** tab gives a library-wide summary.

### Summary cards

You can see:

- total books indexed
- total pages
- average pages per book
- smallest indexed book by page count
- largest indexed book by page count

### Breakdown tables

The page also shows counts grouped by:

- language
- author
- year
- category

### Refresh behavior

The Stats tab loads when you open it. If new books have been indexed since the page was opened, refresh the browser page to load the latest totals.

## Tips and tricks

- Start broad, then narrow with facets.
- Use author names or exact title words when you already know the book you want.
- Use uncommon phrases from the text when you are trying to rediscover a passage.
- If a result includes highlighted snippets, scan those before opening the PDF.
- Check the **Status** tab if new books are not appearing in search yet.
- Check the **Stats** tab when you want a quick sense of collection coverage by language, author, year, or category.

## Need more help?

- For deployment and troubleshooting: [Admin Manual](admin-manual.md)
- For release documentation and screenshots: [v0.4.0 Feature Guide](features/v0.4.0.md)
