# FutrBridge — website

Marketing site for **FutrBridge LLC**, an AI research and AI talent firm based in
San Francisco and the Bay Area (futrbridge.com).

Static HTML/CSS/JS — no build step, no dependencies, no framework.

## Pages

| URL         | File                 | Purpose |
|-------------|----------------------|---------|
| `/`         | `index.html`         | Landing page — positioning, the two division tabs, approach, process, contact |
| `/research` | `research/index.html`| AI Research division |
| `/talent`   | `talent/index.html`  | AI Talent division |
| `/terms`    | `terms/index.html`   | Terms of Use |
| `/privacy`  | `privacy/index.html` | Privacy Policy |

Clean URLs come from the folder layout: `research/index.html` is served at `/research`
by every static host (Netlify, Vercel, Cloudflare Pages, GitHub Pages, S3+CloudFront,
nginx with `index index.html;`). No rewrite rules needed.

## Shared assets

- `assets/css/styles.css` — all styling, driven by CSS custom properties in `:root`.
  Change the brand colours in one place (`--accent`, `--accent-2`, `--accent-3`).
- `assets/js/main.js` — sticky header, mobile nav, scroll reveal, footer year.

The header and footer markup is duplicated across pages (that is the cost of having no
build step). If you change one, change all five.

## Run locally

```sh
python3 -m http.server 8000
# then open http://localhost:8000
```

Serving from a directory root is required for the `/research` and `/talent` links to
resolve — opening the files directly with `file://` will break those links.

## Before going live — replace the placeholders

Everything below was invented as a sensible default and needs your real values:

1. **Social URLs.** Each page's footer has a `<!-- TODO -->` above the LinkedIn and
   YouTube links (`https://www.linkedin.com/company/futrbridge`,
   `https://www.youtube.com/@futrbridge`). Swap in the real ones.
2. **Email addresses.** `hello@`, `research@`, `talent@`, `legal@` and `privacy@
   futrbridge.com` are used throughout. Point them at real inboxes or change them.
3. **Street address.** The footer says only "San Francisco, California".
4. **Landing page stats.** The four figures in the "Why both" section
   (`2`, `SF`, `100%`, `<21d`) are illustrative — replace with real numbers or remove
   the block.
5. **Legal copy.** `/terms` and `/privacy` are drafts, not legal advice, and each
   carries a visible template notice. Have counsel review them, then delete the
   `.legal__note` paragraph from both pages.
6. **Open Graph image.** Each page declares `og:` tags but no `og:image`. Add a
   1200×630 image and an `<meta property="og:image">` tag.

## Accessibility & performance notes

- Skip link, landmark elements, `aria-current` on the active nav item, labelled
  icon-only links, and visible focus rings.
- `prefers-reduced-motion` disables all animation and scroll reveal.
- Responsive from 320px up; the nav collapses to a sheet below 820px.
- Only external request is Google Fonts (Inter + JetBrains Mono). Self-host them if
  you want a zero-third-party page.
