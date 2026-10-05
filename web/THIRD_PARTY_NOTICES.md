# Third-party browser libraries

These files are vendored so the local reader has no runtime CDN dependency.

| Library | Version | Files | License | Source |
|---|---|---|---|---|
| Marked | 18.0.14 | `vendor/marked.umd.js` | MIT, `vendor/marked.LICENSE.md` | [Official release](https://github.com/markedjs/marked/releases/tag/v18.0.14); bundle and license copied from the `marked@18.0.14` npm tarball after SHA-512 integrity verification |
| DOMPurify | 3.4.16 | `vendor/purify.min.js` | Apache-2.0 or MPL-2.0; included `vendor/DOMPurify.LICENSE` is Apache-2.0 | [DOMPurify release](https://github.com/cure53/DOMPurify/releases/tag/3.4.16); downloaded from that tag's `dist/purify.min.js` |

Marked parses Markdown but does not sanitize it. The reader sanitizes its output using DOMPurify before inserting it. See the [Marked usage guidance](https://marked.js.org/) and [DOMPurify documentation](https://github.com/cure53/DOMPurify).

Pinned SHA256 values:

```text
21568877a938d2c4e7d74e27f18e60da96bb73a68809610ca39216e1efebae62  vendor/marked.umd.js
2c90a9b46d6463f26038a29b686e82bc91de01fdac9d5229e7cfe3b360134ea2  vendor/purify.min.js
```
