# Parker metadata fixes

- Preserve the raw filename stem as the fallback title for unknown patterns so special characters like underscores are not normalized away.
- Only infer `category/author` from directory structure when the relative path is exactly two levels deep; deeper archive paths should keep the top-level category and leave author unknown unless the filename supplies one.
- Treat year ranges such as `1885 - 1886` as series metadata rather than a single publication year, and normalize short lowercase category acronyms like `bsal` to uppercase when used as categories.
