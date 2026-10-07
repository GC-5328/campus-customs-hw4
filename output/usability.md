# Campus Customs — Usability Improvements (Problem 9)

Four changes, each logged as it was implemented: what changed, why it helps shoppers, where the code is, and how it was checked.

| # | Area | Improvement | Status |
|---|---|---|---|
| 1 | Front end | Search bar on Products | ✅ done |
| 2 | Front end | Size stock on the product page | ✅ done |
| 3 | Back end | Out-of-stock fallback in the agent | ✅ done |
| 4 | Back end | Short replies, no off-topic answers (faster) | ✅ done |

---

## 1. Search bar on Products (front end)

**Problem:** the Products page was one long grid of 102 items. To find "a hoodie" or "the Game shirt" you had to scroll and scan every card.

**What changed:**
- **Search box** above the grid. It filters **as you type**, with no submit button and no page reload. Every word must match the product's **name**, **type** (`garment_type`), or **search tags**. Tags are included so theme searches work: "game shirt" → *2025 Yale Vs Harvard T Shirt* (tagged "The Game"), and "franklin" → the 3 Benjamin Franklin items.
- **Forgiving matching:** case-insensitive, with plurals trimmed ("Hoodies" = "hoodie") and shopper words mapped to catalogue words ("tee" → "t-shirt"). These rules match the agent's `search_products`, so the box and the chat find the same things.
- **Type shortcuts:** one-click chips for Hoodies, Crewnecks, Tees, Quarter-zips, and Jackets. Clicking an active chip again clears it.
- **Result count:** "27 of 102 items match 'hoodie'". It's announced to screen readers (`aria-live`).
- **Empty state:** "No products match 'xyz'". It suggests a type or the chat and has a *Show all products* button, so there's no dead end.
- **Clear (×) button,** and the search is kept in the URL (`/products?q=hoodie`), so the link can be shared and the browser's Back button returns to it. Cards also remember the list they were opened from, so the product page's back link reads **"← Back to 'hoodie'"** and returns to the same filtered list instead of the full catalogue.

**Why it's fast:** the catalogue is already loaded for the grid, so filtering happens in the browser, with **no extra API calls** and an instant result on each keystroke. With 102 products this is cheaper and quicker than a server round trip.

**Code:** `frontend/src/productSearch.ts` (matching rules, type shortcuts), `frontend/src/pages/Products.tsx` (search box, chips, count, empty state), `frontend/src/index.css` (*Products search* styles).

**Checked:** the filter was run against the live catalogue:

| Query | Matches | Notes |
|---|---|---|
| `hoodie` / `Hoodies` | 27 | same as the agent's search |
| `tee` | 25 | synonym → t-shirt |
| `crewneck` | 29 | |
| `quarter-zip` | 12 | |
| `jacket` | 8 | |
| `game shirt` | 2 | The Game tee + Gameday hood |
| `bulldog hoodie` | 2 | both words must match |
| `xyz123` | 0 | empty state shown |

Browser test (headless Chrome):
- Typing "hoodie" updates the grid to 27 and the URL to `?q=hoodie`.
- "game shirt" shows the Game tee.
- "xyz123" shows the empty state, and its button restores 102.
- The Tees chip shows 25 with the chip highlighted.
- Opening a result and clicking the back link returns to the filtered list.

---

## 2. Size stock on the product page (front end)

**Problem:** shoppers couldn't easily tell which sizes were actually available. A sold-out size looked about the same as one in stock, so someone could pick a size that's gone and only find out at the counter.

**What changed:** the sizes are now a **size picker** (one button per size) on the product page:
- **Every size shows how many are left:** "20 left", or "**Only 5 left**" in amber at 5 or fewer (the same low-stock threshold the agent uses), or "Sold out".
- **Sizes at 0 are greyed out and disabled:** grey dashed box, struck-through size, a `not-allowed` cursor, the native `disabled` attribute (so they can't be clicked, tabbed to, or selected), and a "M is sold out" tooltip.
- **Summary line:** "5 of 6 sizes in stock · 65 total" gives availability at a glance.
- **Picking a size** highlights it and confirms the count: "Size XXL: 5 left, grab it soon. Come by 57 Broadway or ask us in chat." (There's no cart yet, so this is the call to action.)
- **All sizes sold out:** the grid is replaced by a red "Sold out in every size right now." banner. *No product is fully sold out in the current data, so this case wasn't seen in a browser.*
- **Accessibility:** the buttons form a `radiogroup` with `aria-checked`, and the selection line is `aria-live`, so screen readers hear the count.

**Why it helps:** shoppers see stock *before* deciding, can't choose a size that doesn't exist, and "only 5 left" nudges them to act. It's the same data the chat agent quotes (`inventory.quantity`), so the page and the chat never disagree.

**Code:** `frontend/src/pages/ProductDetail.tsx` (`SizePicker`, `stockLabel`, context-aware back link), `frontend/src/components/ProductCard.tsx` (remembers where the card was opened from), `frontend/src/index.css` (`.size-option`, `.sold-out`, `.low`, `.selected`).

**Checked (browser, Crew Left Chest Hoodie):**
- The picker shows `XS 20 left · S 12 left · M Sold out · L 8 left · XL 20 left · XXL Only 5 left`, and every count matches `GET /api/products/crew-left-chest-hoodie`.
- M is `disabled`, greyed, struck through, with a `not-allowed` cursor, and clicking it selects nothing.
- Picking an in-stock size shows "Size XS: 20 left…".

---

## 3. Out-of-stock fallback (back end, agent)

**Problem:** asked for a sold-out size, the agent said "M is sold out" and listed the other sizes. That's correct, but the shopper still had to work out what to do next. That's a dead end, especially if they *need* a medium.

**What changed:**
- **`check_stock` now computes the fallback itself** (`backend/tools.py`). When the requested size is sold out, the result includes:
  - `closest_sizes_in_stock`: up to 2 in-stock sizes of **the same item**, nearest first (M → L, then S). Ties go to the bigger size, since sizing up is the usual advice.
  - `similar_in_stock`: up to 3 **similar items that have the requested size**. "Similar" means the same garment family (hoodie, crewneck, t-shirt, quarter-zip, jacket, long-sleeve), ranked by shared colors and tags, then by closest price. Each one includes its price and the quantity in that size.
- **Sizes we don't make** (XXXL, 3XL, XXS) map to the nearest real size: XXXL → XXL, XXS → XS.
- **A whole item sold out** returns similar items in any size.
- **The `note`** spells out the next step for the model: *"Size M is SOLD OUT. Closest sizes in stock: L (8 left), S (12 left). Similar items with M in stock: Sailing Left Chest Hoodie ($68, 25 left), … Offer ONE of these."*
- **Prompt** (`prompts/prompt.md` → *Sold out, so never leave them at a dead end*): say it's sold out, then offer **one** best option (the nearest size or a similar item in their size), and show both items as chat cards.
- **New return types** in `backend/models.py`: `SimilarItem` and the new `StockCheck` fields. All prices and counts come from the database, so the grounding validator (Problem 6) still checks every number in the reply.

**Why it helps:** every "sold out" answer now comes with a concrete next step and a clickable card. The alternatives are computed in code from live inventory, so they're always really in stock, never guessed by the model.

**Checked:**
- Offline (`test_tools.py`): M → L then S; the similar items are hoodies whose M quantity matches the database and is > 0; XXXL → XXL; an in-stock size gets no fallback noise.
- Live replies:

| Shopper asks | Agent replied | Cards |
|---|---|---|
| "Do you have the Crew Left Chest Hoodie in a medium?" | "Medium is sold out in the Crew Left Chest Hoodie. The Sailing Left Chest Hoodie is a close match in M, with 25 left, for $68." | Crew Left Chest, Sailing Left Chest |
| On the Ice Hockey hoodie page: "Is this in stock in large?" | "Large is sold out in the Ice Hockey Left Chest Hoodie. The Squash Left Chest Hoodie is available in L for $68, with 25 left." | Ice Hockey, Squash |
| "Do you have the Basic Hoodie Big Yale in XXXL?" | "The Basic Hoodie Big Yale isn't made in XXXL. XXL is the closest size, with 25 left; XL is also available, but only 2 left." | Basic Hoodie |

---

## 4. Short replies and no off-topic answers, for faster responses (back end, agent)

**Problem:** replies ran 20–35 words and repeated details the product cards already show. Off-topic questions ("capital of France?", "write my cover letter") took about 5 seconds just to say no. Tracing the agent's messages showed why: **every turn made at least one wasted model round trip.**
- For "What's the capital of France?" and even "Hi there!", the model ran `search_products("France")` before answering. PydanticAI's default structured output is a `final_result` *tool*, so the model is told it **must call a tool** (`tool_choice="required"`), and it spent that call on a pointless catalogue search.
- For "Is the Crew Left Chest Hoodie in M?" it ran `search_products` first, then `check_stock`, even though `check_stock` accepts a product name.

**Baseline** (`backend/bench_chat.py`, 7 questions × 3 rounds, Portkey cache bypassed so each call really hits the model):

| | median time | mean time | median reply | model requests |
|---|---|---|---|---|
| On-topic (4 questions) | 5.5 s | 5.5 s | 22 words | 2–3 |
| Off-topic (3 questions) | 4.9 s | 5.3 s | 29 words | 2 |

**What changed:**
1. **Native structured output** (`agent.py`: `output_type=NativeOutput(AgentReply)`). The reply now comes back as JSON-schema text instead of a forced tool call, so the model only calls tools when it actually needs data. Off-topic messages and greetings take **1 model request** instead of 2.
2. **Off-topic gate first** (`prompts/prompt.md` → *First: is this about the shop?*): the first thing the model decides is whether the message is about the shop. If not, it replies with one decline-and-redirect sentence and **calls no tools**: "That's outside what I can help with. Can I help you find some Yale gear instead?" No explanations and no partial help (rule 1 in *Safety rules*).
3. **Fewest tool calls** (prompt → *Tools*): if the shopper names a product, or it's the one on their page, call `get_product_info` / `check_stock` directly with the name. Search only when browsing or when the product is unclear, and make independent lookups in the same step.
4. **Short replies** (prompt → *Voice*): at most 2 sentences / about 40 words, one fact plus one next step. The cards carry the details, so no repeated descriptions or size lists, and lists are capped at 3 lines.
5. **Model settings** (`agent.py` → `MODEL_SETTINGS`): `openai_text_verbosity="low"` and `openai_reasoning_effort="low"`. The default is configurable with `REASONING_EFFORT`. I measured `none` too: it wasn't faster (off-topic 2.2 s vs 1.6 s), so `low` stays. `minimal` isn't supported by gpt5.6-luna (HTTP 400). No custom temperature, as required.

**After** (same benchmark, same 7 questions × 3 rounds, cache bypassed):

| | median time | mean time | median reply | model requests |
|---|---|---|---|---|
| On-topic | **4.4 s** (−20%) | 4.9 s | **20 words** | 2 |
| Off-topic | **1.6 s** (−67%, ~3× faster) | 1.8 s | **17 words** (−41%) | **1** |

Sample replies after the change:
- "How much is the Basic Hoodie Big Yale?" → "The Basic Hoodie Big Yale is $68. Want me to check a specific size?" (14 words)
- "Can you help me write a cover letter?" → "That's outside what I can help with. Can I help you find some Yale Bulldog gear instead?" (1.3 s)

**Why it helps:** off-topic chat is answered almost instantly and can't wander, shop answers arrive about a second sooner, and short replies are quicker to read. The cards next to them carry the detail.

**Side finding:** Portkey caches identical requests, so repeating a question returned in about 0.2 s. That's great for shoppers asking common questions, but it hides real model latency in benchmarks. `bench_chat.py` runs against a server started with `PORTKEY_CACHE_REFRESH=1` (`agent.py` adds the `x-portkey-cache-force-refresh` header only when that's set).

**Checked after switching the output mode** (it touches every reply):
- `test_tools.py`: 32 offline checks (the fake model now returns JSON text).
- `test_auth.py`: all pass.
- `test_chat.py`: 27 live checks, including price and stock grounding, the sold-out fallback, page results, page context, and memory.
- Browser tests: chat → results page and memory/page context still pass.
- One live check first failed only because the test didn't recognise "isn't" (curly apostrophe) as a "no". The reply itself, "This hoodie isn't available in pink, it comes in navy blue and white", was right, so the test was fixed.

---

## Summary

| Improvement | Before | After |
|---|---|---|
| Find a product | Scroll 102 cards | Type "hoodie" → 27 cards instantly; chips; shareable `?q=` |
| Size availability | Small text, sold-out sizes look clickable | Size picker: "N left" / "Only N left", sold-out sizes greyed and disabled |
| Sold-out size in chat | "M is sold out." (dead end) | "M is sold out. L has 8 left, or the Sailing Left Chest Hoodie ($68) has 25 in M." with cards |
| Off-topic question | ~4.9 s, 29 words, wasted catalogue search | **~1.6 s**, 17 words, no tools |
| On-topic question | ~5.5 s, 2–3 model requests | **~4.4 s**, 2 requests |
