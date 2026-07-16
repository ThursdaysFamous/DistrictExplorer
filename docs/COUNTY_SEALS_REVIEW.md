# Illinois county seals — coverage & review list

_Marker art for the selection pin: when a clicked/searched point lands in a
county outside the City of Chicago, the pin becomes that county's seal
(`COUNTY_SEAL_URLS` in `index.html`). This tracks all 102 Illinois counties:
which now ship a seal, and — for those that don't — exactly why, so the gaps
can be filled or waived deliberately._

**Hard rule (from `icons/source/README.md`): only cleanly-licensed art ships —
public domain or an explicit free license (CC0/CC BY/CC BY-SA). A seal that
exists only as a non-free "fair use" upload, or only on a county's own
website with no free license, is _not_ shippable without permission and is
listed below rather than used.**

Counts: **9 shipped** · **4 free-flag (awaiting your OK)** · **15 non-free seal exists** · **74 no image found** (= 102 total).

Search method: Wikimedia Commons (title + full-text) plus each county's
English Wikipedia infobox, with license metadata pulled per file. Non-free
status was confirmed via the en.wikipedia imageinfo `repository=local` +
`Fair use` tags.

---

## ✅ Shipped (9 counties, cleanly licensed)

| County | Marker | License |
|---|---|---|
| Cook County | `icons/seals/cook-county.png` — seal (pre-existing) | Public domain |
| Hamilton County | `icons/seals/hamilton.png` — seal | Public domain |
| Kane County | `icons/seals/kane.png` — seal | Public domain |
| Lake County | `icons/seals/lake.png` — seal | Public domain |
| Macon County | `icons/seals/macon.png` — seal | Public domain |
| Saline County | `icons/seals/saline.png` — seal | Public domain |
| St. Clair County | `icons/seals/st-clair.png` — seal | CC BY-SA 4.0 |
| Washington County | `icons/seals/washington.png` — seal | CC BY-SA 4.0 |
| Will County | `icons/seals/will.png` — seal | CC BY-SA 4.0 |

Provenance (source file + author/attribution) for each is in `icons/source/README.md`.

---

## 🟡 Free county **flag** available — no free seal (4 counties)

For these, no freely-licensed *seal* exists, but a genuine, freely-licensed
county **flag** is on Wikimedia Commons. **Decision: not shipped — the marker set
is seals only.** These are recorded here so the option stays on the table: if a
flag is ever acceptable as a stand-in, each is a one-line add (drop the derived
PNG in `icons/seals/`, add a `COUNTY_SEAL_URLS` entry). Until then these counties
keep the plain name-badge fallback.

| County | Free flag (Commons) | License |
|---|---|---|
| Franklin County | [Flag of Franklin County, Illinois.svg](https://commons.wikimedia.org/wiki/File%3AFlag_of_Franklin_County%2C_Illinois.svg) | CC BY-SA 4.0 |
| McHenry County | [McHenry County, Illinois flag.gif](https://commons.wikimedia.org/wiki/File%3AMcHenry_County%2C_Illinois_flag.gif) | CC BY-SA 4.0 |
| Peoria County | [Flag of Peoria County, Illinois.svg](https://commons.wikimedia.org/wiki/File%3AFlag_of_Peoria_County%2C_Illinois.svg) | Public domain |
| Sangamon County | [Flag of Sangamon County, Illinois.svg](https://commons.wikimedia.org/wiki/File%3AFlag_of_Sangamon_County%2C_Illinois.svg) | CC BY-SA 4.0 |

---

## 🔴 A seal exists, but it's **non-free** (15 counties)

Each of these counties *does* have a seal/flag/logo online, but only as a
**non-free "fair use" upload on English Wikipedia** (not on Commons, no free
license). Shipping it would violate the repo's licensing rule. To cover these,
someone needs to obtain the seal under a free license — e.g. ask the county
clerk to release it (public domain / CC0), or find a free-licensed rendering.

| County | Non-free file (English Wikipedia) | Status |
|---|---|---|
| Adams County | [AdamsCountyILseal.png](https://en.wikipedia.org/wiki/File%3AAdamsCountyILseal.png) | Fair-use / not free |
| DeKalb County | [DeKalb County il seal.png](https://en.wikipedia.org/wiki/File%3ADeKalb_County_il_seal.png) | Fair-use / not free |
| DuPage County | [Seal of DuPage County, Illinois.png](https://en.wikipedia.org/wiki/File%3ASeal_of_DuPage_County%2C_Illinois.png) | Fair-use / not free |
| Edgar County | [Seal Edgar County, Illinois.png](https://en.wikipedia.org/wiki/File%3ASeal_Edgar_County%2C_Illinois.png) | Fair-use / not free |
| Effingham County | [Effingham County Illinois seal.png](https://en.wikipedia.org/wiki/File%3AEffingham_County_Illinois_seal.png) | Fair-use / not free |
| Grundy County | [Seal of Grundy County, Illinois.png](https://en.wikipedia.org/wiki/File%3ASeal_of_Grundy_County%2C_Illinois.png) | Fair-use / not free |
| Jasper County | [The flag for Jasper County, Illinois.png](https://en.wikipedia.org/wiki/File%3AThe_flag_for_Jasper_County%2C_Illinois.png) | Fair-use / not free |
| Marion County | [Flag of Marion County, Illinois.png](https://en.wikipedia.org/wiki/File%3AFlag_of_Marion_County%2C_Illinois.png) | Fair-use / not free |
| McDonough County | [Flag of McDonough County, Illinois.png](https://en.wikipedia.org/wiki/File%3AFlag_of_McDonough_County%2C_Illinois.png) | Fair-use / not free |
| Monroe County | [Seal of Monroe County, Illinois.png](https://en.wikipedia.org/wiki/File%3ASeal_of_Monroe_County%2C_Illinois.png) | Fair-use / not free |
| Rock Island County | [Rock Island County, Illinois logo.jpg](https://en.wikipedia.org/wiki/File%3ARock_Island_County%2C_Illinois_logo.jpg) | Fair-use / not free |
| Tazewell County | [Tazewell County, Illinois seal.png](https://en.wikipedia.org/wiki/File%3ATazewell_County%2C_Illinois_seal.png) | Fair-use / not free |
| Vermilion County | [Vermilion County Illinois seal.jpg](https://en.wikipedia.org/wiki/File%3AVermilion_County_Illinois_seal.jpg) | Fair-use / not free |
| Whiteside County | [Whiteside County, Illinois Logo.png](https://en.wikipedia.org/wiki/File%3AWhiteside_County%2C_Illinois_Logo.png) | Fair-use / not free |
| Winnebago County | [Winnebago County il seal.png](https://en.wikipedia.org/wiki/File%3AWinnebago_County_il_seal.png) | Fair-use / not free |

---

## ⚪ No seal image found online (74 counties)

No seal, flag, or logo for these counties turned up on Wikimedia Commons or in
their English Wikipedia infobox (most infoboxes show a courthouse photo, not a
seal). Some of these counties may still have a seal on their **official county
website**; those weren't used because their copyright status is unverified and
the repo ships only cleanly-licensed art. These need a source *and* a free
license (ideally a public-domain release from the county) before they can ship:

| Alexander County | Fayette County | Lawrence County | Pope County |
|---|---|---|---|
| Bond County | Ford County | Lee County | Pulaski County |
| Boone County | Fulton County | Livingston County | Putnam County |
| Brown County | Gallatin County | Logan County | Randolph County |
| Bureau County | Greene County | Macoupin County | Richland County |
| Calhoun County | Hancock County | Madison County | Schuyler County |
| Carroll County | Hardin County | Marshall County | Scott County |
| Cass County | Henderson County | Mason County | Shelby County |
| Champaign County | Henry County | Massac County | Stark County |
| Christian County | Iroquois County | McLean County | Stephenson County |
| Clark County | Jackson County | Menard County | Union County |
| Clay County | Jefferson County | Mercer County | Wabash County |
| Clinton County | Jersey County | Montgomery County | Warren County |
| Coles County | Jo Daviess County | Morgan County | Wayne County |
| Crawford County | Johnson County | Moultrie County | White County |
| Cumberland County | Kankakee County | Ogle County | Williamson County |
| De Witt County | Kendall County | Perry County | Woodford County |
| Douglas County | Knox County | Piatt County |  |
| Edwards County | LaSalle County | Pike County |  |

---

## How to add a seal once a free source is found

1. Save the full-res original to `icons/source/<slug>-seal.<ext>`.
2. Derive the 128×128 marker PNG:
   - SVG: `node scripts/render_seal_svg.mjs icons/source/<slug>-seal.svg icons/seals/<slug>.png 128`
   - Raster: `python3 scripts/convert_raster_seal.py icons/source/<slug>-seal.<ext> icons/seals/<slug>.png [--trim] [--knockout]`
3. Add one line to `COUNTY_SEAL_URLS` in `index.html`, keyed by the exact TIGER
   name (`"<County> County": "icons/seals/<slug>.png"`).
4. Record source + license + author in `icons/source/README.md`, and move the
   county out of this list.

_Generated as part of the statewide county-seal pass; counts and lists reflect
a Commons + Wikipedia sweep of all 102 counties._
