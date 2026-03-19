# User Manual

This manual explains how to use Aithena as a reader or library user. For setup, deployment, and service troubleshooting, see the [Admin Manual](admin-manual.md). For the latest release features, see the [v1.9.1 Release Notes](release-notes/v1.9.1.md).

**v1.9.0 introduces account management and role-based access control.** Users can now manage their own passwords, and access is enforced by role (admin, user, viewer). See [Your Account & Permissions](#your-account--permissions) below.

## Getting started

Aithena is a web app for searching an indexed PDF library. It helps you:

- sign in with the account created during installation (v0.11.0+)
- search by keyword, semantic meaning, or a hybrid of both
- narrow results with facets
- open PDFs directly from search results
- use Similar Books recommendations after opening a document
- upload PDF files via drag-and-drop (v0.6.0+)
- check the Aithena version in the footer (v0.7.0+)
- check system health in the Status tab
- view library-wide statistics in the Stats tab
- open the Admin tab to load the embedded operator dashboard when you need admin tools

### How to access it

Most users will open Aithena through the main web address provided by their administrator.

In a local Docker Compose setup, the main entry point is usually:

- `http://localhost/`

If you are running the frontend in Vite development mode instead of the full stack, the UI may also be available on:

- `http://localhost:5173`

With the v0.11.0 auth flow enabled, visiting protected pages redirects you to `/login` until you sign in successfully.

### Sign in (v0.11.0+)

1. Open the main Aithena URL.
2. Enter the username and password created by the installer.
3. Submit the login form.
4. After login, Aithena keeps your browser session active and automatically attaches auth to protected requests until you log out or the session expires.

![Aithena login page](images/login-page.png)

<!-- TODO: capture screenshot -->

### Reset your password

If you forget your password, an administrator can reset it using the CLI tool:

```bash
# From the project root — generates a new random password and prints it
cd src/solr-search
uv run python reset_password.py --db-path /data/auth/users.db

# Or set a specific password
uv run python reset_password.py --db-path /data/auth/users.db --password "your-new-password"

# Reset a specific user (default is "admin")
uv run python reset_password.py --db-path /data/auth/users.db --username myuser --password "new-pass"
```

On a local dev machine, the database is typically at `~/.local/share/aithena/auth/users.db`. In Docker, it's at `/data/auth/users.db` inside the `solr-search` container.

To reset the password inside a running container:

```bash
docker compose exec solr-search python reset_password.py
```

The tool generates a secure 32-character random password if `--password` is omitted, and prints it to stdout.

![Aithena tab navigation](images/tab-navigation.png)

## Your Account & Permissions

*New in v1.9.0:* Users can now manage their own accounts with self-service password changes and profile viewing. Access to library features depends on your role.

### Manage your password (v1.9.0+)

You can change your password at any time:

1. Open the **Profile** page by clicking your username in the top navigation profile menu or navigating to `/profile`
2. Enter your current password to verify your identity
3. Enter a new password that meets the **strong password policy**:
   - **At least 10 characters** (increased from 8 in earlier versions)
   - **At least 3 of the 4 complexity categories:**
     - Uppercase letters (A–Z)
     - Lowercase letters (a–z)
     - Digits (0–9)
     - Special characters (!@#$%^&* etc.)
   - **Cannot contain your username**
4. Confirm the new password by re-entering it
5. Click **Update Password** to save

Verify your password meets the policy requirements after entry.

### View your profile (v1.9.0+)

1. Click your username in the top navigation profile menu or navigate to `/profile`
2. View your account details:
   - **Username** — your login name
   - **Role** — your access level in the system (see table below)
   - **Created** — when your account was created
3. Use the **Change Password** form to update your password (see above)

### Understanding roles and permissions (v1.9.0+)

Aithena uses three roles to control what you can do:

| Role | Can Search | Can Upload | Can View Profile | Can Manage Users | Library Limits |
|------|-----------|-----------|------------------|-----------------|----------------|
| **admin** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes (full CRUD) | None |
| **user** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No | None |
| **viewer** | ✅ Yes (read-only) | ❌ No | ✅ Yes | ❌ No | Search only |

**What this means:**
- **Admin** users can create, edit, and delete other user accounts, in addition to full search and upload capabilities
- **User** (standard) role is suitable for day-to-day library access — search, upload PDFs, and manage your own password
- **Viewer** role is for read-only access — you can search the library but cannot upload documents or manage users

If your role is more restrictive than you expect, contact your administrator to request role changes.

### Login rate limiting

If you enter your password incorrectly **5 or more times within 60 seconds**, the system will reject further login attempts from your IP address for that window. If you exceed the limit, wait a moment and try again.

If you suspect your account has been compromised, contact your administrator to reset your password.

## Searching for books

The **Search** tab is the main place to work.

*New in v1.8.1:* All text on this page, including labels, buttons, and placeholders, is now fully translated. The page automatically displays in your selected language.

![Search page before querying](images/search-page.png)

### Run a search

1. Open **Search**.
2. Enter one or more keywords.
3. Pick a search mode if you want something other than the default.
4. Click **Search**.

### Search modes

Use the mode buttons beside the search box to switch between:

- **Keyword** — best for exact words, known titles, author names, and traditional full-text lookup.
- **Semantic** — best when you want books that are conceptually related to a phrase or topic, even if they do not share the exact same wording.
- **Hybrid** — combines both approaches and is usually the best starting point when you want broad discovery with some precision.

Important behavior in the shipped UI:

- **Keyword** is the default mode when the page opens.
- Switching modes keeps your current query but resets results back to page 1.
- The current mode is shown again next to the result count as a badge.
- Semantic and hybrid search require a real query. If embeddings are not ready yet, the page shows an inline error instead of silently failing.

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

### Shareable search links (v1.3.0+)

Your current search, including filters, sort order, and page number, is automatically encoded in the URL. This makes it easy to share results with colleagues.

#### How to share a search

1. Run a search with your filters, sort, and page selection exactly as you want them.
2. Copy the URL from your browser's address bar.
3. Send the URL to a colleague via email, chat, or any messaging tool.
4. When they open the link, they'll see the exact same filtered results without re-running the search.

#### Browser history

- Use your browser's **back** button to return to a previous search.
- Use your browser's **forward** button to move forward through your search history.
- Each change to filters, sort order, or page number is tracked in the browser history, so you can step through your search workflow.

#### What gets saved in the URL

The URL encodes:

- your search query
- all active filters (language, author, year, category)
- sort order (relevance, year, title, author)
- current page number
- results per page (10, 20, or 50)

![Search results with book cards](images/search-results.png)

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

![Filtered search results](images/facet-panel.png)

## Viewing PDFs

When a result includes an attached document link, you can open the PDF directly from the result card.

*New in v1.8.1:* All text on this page, including labels and buttons, is now fully translated to your selected language.

### Open a PDF

1. Run a search.
2. Find the result you want.
3. Click **📄 Open PDF**.

The document opens in an overlay viewer without leaving the search page.

![PDF viewer with document open](images/pdf-viewer.png)

### Page navigation from search results

If the search result includes matched page information, Aithena opens the PDF on the first matching page automatically. This is useful when you searched for a term that appears deep inside a long document.

### Close the viewer

You can close the PDF overlay by:

- clicking the **✕** button
- pressing **Escape** on your keyboard

### If a PDF does not load

If the embedded viewer cannot display the file, Aithena shows a fallback link so you can try opening the PDF in a new browser tab.

## Finding similar books

The **Similar Books** panel appears after you open a book from the search results.

### Where to find it

1. Run any search.
2. Click **📄 Open PDF** on a result.
3. Look below the search results area for the **Similar Books** panel.

### How it works

- The panel loads up to **5** semantically related books for the document you just opened.
- Each card shows the title, author, optional year/category, and a rounded match score such as **91% match**.
- While the request is running, the page shows loading text and placeholder cards.
- If no recommendations are available, the panel says **No similar books found**.
- If the request fails, the page shows a friendly message instead of breaking the rest of the search UI.

### How to use recommendations

Click any similar-book card to replace the currently selected PDF with that recommendation. This makes it easy to explore related titles without starting a new search from scratch.

![Similar Books recommendations](images/similar-books.png)

<!-- TODO: capture screenshot -->


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
- **ZooKeeper** — coordination service for search nodes
- **RabbitMQ** — queue service used by the ingestion pipeline
- **Redis** — indexing state store
- **embeddings-server** — semantic search backend

*New in v1.8.1:* The Status tab now reports all critical services, including previously missing services like ZooKeeper and embeddings-server.

### Auto-refresh

The Status tab refreshes automatically every **10 seconds**, so it is the best place to watch the system during imports or after operational changes.

![System status page](images/status-tab.png)

## Understanding the Stats tab

The **Stats** tab gives a library-wide summary.

### Summary cards

You can see:

- total books indexed
- total pages
- average pages per book
- smallest indexed book by page count
- largest indexed book by page count

### Accurate book count (v1.4.0+)

Starting with v1.4.0, the **total books indexed** count reflects the actual number of books in your library. Earlier versions counted indexed chunks or pages, which could be much higher than the unique book count. Now the count is precise and useful for library metrics.

### Breakdown tables

The page also shows counts grouped by:

- language
- author
- year
- category

### Refresh behavior

The Stats tab loads when you open it. If new books have been indexed since the page was opened, refresh the browser page to load the latest totals.

![Collection statistics](images/stats-tab.png)

## Using the Admin tab

The **🛠️ Admin** tab opens an embedded operator dashboard inside the Aithena app.

### What it shows

The embedded Streamlit dashboard currently includes:

- **Total Documents**, **Queued**, **Processed**, and **Failed** counters
- **RabbitMQ Queue** metrics for ready, unacknowledged, and total messages
- sidebar access to **Document Manager**, where operators can inspect queued, processed, and failed documents and trigger requeue or clear actions

### What to expect

- The Admin tab loads `/admin/` inside the app rather than sending you to a different product.
- It is mainly intended for operators and library administrators, not day-to-day readers.
- The admin dashboard now requires an authenticated session; if your session expires, Aithena redirects you back to `/login`.
- If the dashboard cannot load after you sign in, contact your administrator to confirm the admin services are running and your account has been provisioned correctly.

*New in v1.8.1:* The admin dashboard login issue has been fixed. You should now be able to access it without being stuck in a login loop.

![Admin dashboard](images/admin-dashboard.png)

<!-- TODO: capture screenshot -->


## Uploading PDFs (v0.6.0+)

The **Upload** tab lets authenticated users add PDFs to the library without direct server access.

### How to upload

1. Open the **Upload** tab.
2. Either drag-and-drop a PDF onto the zone, or click to browse and select a file.
3. Watch the real-time progress bar as the file transfers.
4. When the upload completes, you'll see a success message.

![PDF upload page](images/upload-page.png)

<!-- TODO: capture screenshot -->

### What happens after upload

- Your PDF is placed in the library staging area.
- The indexer picks it up on the next scan cycle (usually within seconds to minutes depending on queue size).
- Once indexed, the document appears in search results.
- If indexing fails, check the Admin tab to see failed documents.

*New in v1.8.1:* The Upload page now displays all instructions and status messages in your selected language. No more English-only UI text.

### Upload limits

- **File size**: Maximum 50 MB per file (contact your administrator to change this)
- **File type**: PDF only
- **Rate limit**: 10 uploads per minute per IP address

### Troubleshooting uploads

| Error | What it means | How to fix |
|---|---|---|
| "Invalid file type. Please upload a PDF." | You selected a non-PDF file | Select a file ending in `.pdf` |
| "File is too large. Maximum size is 50 MB." | Your PDF exceeds the size limit | Split the PDF or contact your administrator |
| "Too many uploads. Please wait a moment and try again." | You've hit the rate limit | Wait a minute and try again |
| "Upload failed. Please try again." | Server error during upload | Try again; if it persists, contact your administrator |

## Version information (v0.7.0+)

The Aithena version appears in the footer of the web app as a small version badge.

### What the version means

The version (e.g., **v1.8.1**) tells you which release you are running. This is useful when:

- **Troubleshooting:** Knowing the version helps you search documentation for known issues.
- **Feature confirmation:** New features appear only in specific versions (e.g., PDF upload in v0.6.0 and later).
- **Support:** When contacting support, mention your version and the commit hash shown in the tooltip.

*New in v1.8.1:* The version now always matches the shipped release value, even after updates. Earlier versions sometimes showed stale version numbers.

### How to find the version

Hover over the version badge in the bottom-right corner of the footer to see:

- Full version number
- Git commit hash
- Build timestamp

If the version displays as "unknown", the admin dashboard may not be running or the version endpoint is unavailable.

## Tips and tricks

- Start broad, then narrow with facets.
- Use author names or exact title words when you already know the book you want.
- Use uncommon phrases from the text when you are trying to rediscover a passage.
- If a result includes highlighted snippets, scan those before opening the PDF.
- Check the **Status** tab if new books are not appearing in search yet.
- Check the **Stats** tab when you want a quick sense of collection coverage by language, author, year, or category.
- Upload PDFs via the **Upload** tab if you don't have direct server access (v0.6.0+).
- Check the footer version badge to confirm you're running the latest release (v0.7.0+).

## Need more help?

- For deployment and troubleshooting: [Admin Manual](admin-manual.md)
- For release documentation and features: [v0.7.0 Feature Guide](features/v0.7.0.md)
- For previous releases: [v0.6.0 Feature Guide](features/v0.6.0.md), [v0.5.0 Feature Guide](features/v0.5.0.md)
