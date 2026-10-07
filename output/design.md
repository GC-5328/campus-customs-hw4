# Campus Customs — Design (Problem 10)

## Why this design

Light nav and open space keep the product in front of them, so they don't bounce off a cluttered first screen. One line and one Shop button on Home get them to the rack fast.

Big photos and a wide grid are easy to scan. Price sits right under the name. A small fade on hover shows the card is clickable without jumping around.

On the product page, image, price, sizes, and one blue Add to bag button. Sizes at 0 are grey, so customers don't tap something they can't buy and leave. Chat stays a small corner button, so they can ask about a size without covering the item. These changes clean up the user experience with very clear next steps, which would keep customers engaged while encouraging them to buy.

---

## Design system

| Token | Value | Used for |
|---|---|---|
| Page background | `#f5f5f7` | `body`, chat header, agent chat bubble, sold-out pill |
| Surface | `#ffffff` | Product cards, product page panel, chat panel, forms, bag |
| Text | `#1d1d1f` | All body text, headings, black wordmark |
| Secondary text | `#6e6e73` | Nav links, card prices, card one-liners, hints |
| Hairline | `#d2d2d7` / `rgba(0,0,0,.08)` | Nav bottom border, pill and input borders |
| **Yale blue** | `#00356B` | Links, Shop / Add to bag buttons, active nav item, user chat bubble, chat launcher |
| **Accent** | `#8B1E3F` | **Out of stock only**: the "Sold out" pill label, "Sold out in every size", "You have all N in your bag" |
| Error | `#d70015` | Form and request errors only, kept separate so the accent always means "out of stock" |
| Font | Inter 400/500/600/700, Google Fonts | Everything. Body 17px, line-height 1.47 |
| Headings | 600–700, letter-spacing −0.022 to −0.03em, line-height 1.1 | H1 `clamp(2.25rem, 4.5vw, 3.5rem)`; Home H1 up to 4.5rem |
| Radius | 18px cards and panels, 12px pills and inputs, 999px buttons | |
| Motion | `200ms ease` opacity fades only | Page fade-in, hover image fade, chat panel and message fade, typing dots fade. `prefers-reduced-motion` turns all motion off |

All of it lives in CSS variables at the top of `frontend/src/index.css`, so the palette can be changed in one place.

## Page by page

**Nav** (`components/NavBar.tsx`): sticky, `rgba(255,255,255,.8)` with `backdrop-filter: saturate(180%) blur(20px)` and a 1px hairline underneath. Black "Campus Customs" wordmark. Home, Products, About Us, Log in, Create account, and Bag are grey text links, and only the **active** one turns Yale blue (no underline bar). Bag shows a small count badge. No blue bar anywhere.

**Home** (`pages/Home.tsx`): centered, with a lot of space around it.
- "Officially licensed Yale gear." in 4.5rem bold.
- One shorter grey line: "Casual comfort, classic Bulldog pride."
- One Yale-blue **Shop Bulldog Blue** button.
- **One** product photo (the Champion Reverse Weave hoodie) below, linked to its product page. `mix-blend-mode: multiply` blends the photo's white background into the page.
- The address moved to a quiet site-wide footer: "57 Broadway, New Haven · Officially licensed Yale gear since 1975".

**Products** (`pages/Products.tsx`, `components/ProductCard.tsx`):
- **Grid:** 3 columns on desktop, 2 on tablet (≤960px), 1 on mobile (≤600px), with 2.5rem × 2rem gaps.
- **Card:** white, 18px radius, a large square image with padding, then the name, the price in grey, and one short line (single-line ellipsis).
- **Hover:** the image fades to 80% opacity over 200ms. No lift, no shadow, no transform.
- **Search box and type chips** were restyled quietly: a white input and outline pills, with the active chip in Yale blue text.

**Product page** (`pages/ProductDetail.tsx`):
- **Layout:** one white panel, image large on the left (1.25fr) and text on the right (1fr). It stacks to one column under 860px.
- **Order:** name → price → description → colors (small grey) → Size → **Add to bag**.
- **Sizes are quiet pills:** white with a hairline, the size plus a tiny "20 left" count, and a dark outline when selected. **A size at 0 is grey and struck through**, on the light-grey fill with no border; its "Sold out" label is the only accent-coloured text; and it's `disabled`, so it can't be clicked.
- **One Yale-blue "Add to bag" button**, full width. It's disabled until a size is picked ("Select a size."), then shows "Size XXL: 5 left, grab it soon." After adding: "Added size XXL to your bag. View bag". The bag never holds more than the stock for that size ("You have all 5 in size XXL in your bag", in the accent colour).

**Bag** (`pages/Bag.tsx`, `BagContext.tsx`): added so "Add to bag" leads somewhere instead of being a dead button. Items are kept in the browser (`localStorage`). The page lists each item (photo, name, size, quantity, line price, Remove) and the subtotal, with the note "Pay and pick up at Campus Customs, 57 Broadway. Online checkout is coming soon." There's no payment step; the site doesn't take payments.

**Chat** (`components/ChatWidget.tsx`):
- **Closed:** a small **round 52px Yale-blue button** with a speech-bubble icon, bottom right, labelled "Ask Campus Customs" for screen readers.
- **Open:** a white panel with a light-grey (`#f5f5f7`) header reading **"Ask Campus Customs"**.
- **Bubbles:** **user `#00356B` with white text, agent `#f5f5f7`**.
- **Motion:** the typing dots now **fade** in turn instead of bouncing.

**Log in / Create account / About:** white cards on the grey page, Inter, inputs with a 12px radius and a Yale-blue focus border, and errors in the separate error red.

## Product photos

74 of the 102 catalogue photos had **solid black backgrounds**, which look like black boxes on white cards. `backend/clean_images.py` makes white-background web copies in `data/products_web/`. The originals in `data/products/` are never changed.

**How it works:**
- It flood-fills near-black pixels (every channel ≤ 10) **connected to the image border** with white. A navy garment is never connected to the border, so it stays intact.
- It also fills **enclosed** pure-black gaps (≤ 8, at least 150 px), such as the space between an arm and the body. If those enclosed fills add up to more than 1.2% of the photo, they're skipped. Measured on all 27 affected photos: real gaps were ≤ 0.92%, while the very dark Basic Hoodie's shadows hit 1.7% and would have been punched with white holes.
- The mask is grown 1px and softened, which hides most of the JPEG fringe.

**Serving:**
- The API serves `data/products_web/` when it exists (`db.IMAGES_DIR`) and falls back to the originals otherwise.
- Image URLs carry a version tag (`?v=web2`) so browsers don't keep showing cached black-background copies.

**Known limit:** a few very dark navy items still have a faint speckled edge where the JPEG fringe was darker than the threshold. Re-exporting those photos would fix it properly.

## What was checked

A headless-Chrome test (`ui_design_test`, 32 checks) read the **computed styles**:
- **Theme:** `#f5f5f7` page, `#1d1d1f` text, Inter actually loaded, 17px body.
- **Nav:** white, blurred, 1px border; black wordmark; grey links; Yale-blue active link with no underline.
- **Home:** the exact headline, one Yale-blue button, one image.
- **Products:** 3 columns on desktop and 1 at 390px wide; white cards with `box-shadow: none`; grey price; one-line description; 200ms opacity transition with no transform.
- **Product page:** white panel; name, price, description order; struck sold-out pill with the `#8B1E3F` label; Add to bag disabled until a size is picked, then the count goes to 1; the stock cap holds at 5.
- **Chat:** round 52px Yale-blue launcher; white panel with `#f5f5f7` header titled "Ask Campus Customs"; user bubble `#00356B` with white text, agent bubble `#f5f5f7`; only `fade-in` / `typing-fade` animations running.
- **Bag:** the item and `$340.00` subtotal shown.

The earlier chat → results page and memory browser tests were re-run on the new markup and pass.
