# Extraction — UI Placement Rules (位置法律)

> **Status:** v1.0 — every number below is **measured from the SuperCasual kit's own demo prefabs**, not invented. The kit is the **absolute standard**.
> **Companion to:** `UI_Visual_Design_Guidelines.md` (tokens) · `Screen_Layout_Specs.md` (per-screen mockups) · `Component_Selection_Matrix.md` (which prefab).
> **Why this doc:** the other docs give tokens + ASCII sketches ("放这附近"). This gives the missing **hard placement law** — where it anchors, how tall, how big, what casing — copied from how Layer Lab actually composed the kit.

## 0. How to read these numbers

- **Source of truth = the kit prefab.** When you place an element, match the kit prefab's own `sizeDelta` / anchor / casing. Do **not** re-scale by eye.
- **Reference frame:** the kit's `DemoScene_SuperCasual` canvas is **CanvasScaler 1080×2340, Match 0.487**. All px below are in that frame. A **ratio** (% of the 1080×2340 screen) is given alongside so the rule transfers to any portrait canvas.
- **Applying to Extraction — RATIFIED (2026-06-14):** kit-based screens use the **kit's own CanvasScaler reference 1080×2340, Match 0.487**, so every measured px below applies **1:1**. (Older specs mention 1440×2560 — for kit screens that is superseded; see [§15](#15-decision-log).) The ratios are still listed for any non-kit canvas.
- **Notation:** `sd` = sizeDelta(w,h); anchor written as a preset name; `aPos` = anchoredPosition; all from the live prefabs.

---

## 1. The five-band spine (measured from `Lobby` / `Shop` / HUD)

| # | Band | Kit height | Ratio | Anchor | Kit evidence |
|---|---|---|---|---|---|
| 1 | **Top resource bar** | **118px** | 5.0% | top-stretch, top-pin | `Lobby/Topbar sd=(0,118) aPos y=-59`; identical in Play_UI_Idle & Shop |
| 2 | **Hero / feature** | flex | ~30% | top-pin under band 1 | `Lobby/Middle` holds character (593×634) + floating btns + banner |
| 3 | **Content / scroll** | fill | — | stretch between 2 & 4 | `Shop/Scroll View sd=(0,-442)` (fills minus chrome) |
| 4 | **Primary action** | ~194–249 | 8–11% | bottom-pin above band 5 | `Lobby/Button_Play` at aPos y=-699 |
| 5 | **Bottom bar** | **180** (main nav) / **121** (sub-tab + Back) | 7.7% / 5.2% | bottom-stretch, bottom-pin | `Lobby/BottomBar_Menu sd=(0,180)`; `Shop/Bottom sd=(0,121)` |

- Chrome bands (1, 5) are **edge-pinned, never centered** — that is exactly how the kit anchors them (`aMin=(0,1)…` top, `aMin=(0,0)…` bottom).
- The kit does **not** force one universal tab bar: a top-level hub (`Lobby`) uses the **180px 5-icon `BottomBar_Menu`**; a drilled-in screen (`Shop`) uses a **121px bar = Back button + sub-tabs**. Pick per screen role.

---

## 2. Top resource bar (band 1) — from `Lobby/Topbar`

- Band height **118**, top-pinned, full width.
- `Group_ResourceBar` height **56**, currency chips in a Horizontal layout, **spacing 90**, **left-aligned** on hub screens (`aPos x=+319` from left); **centered** on gameplay/shop variants.
- Chip widths as authored: Energy **168**, Coin **227**, Gem **175**; currency number `Text` **sz 36**; the inline `+` button is **60×62** pinned to the chip's right.
- **Menu/settings button** top-right: `Button_Menu` **130×122**, anchor top-right, `aPos=(-100,-90)` → **100px from right, 90px from top**.

---

## 3. Bottom bars (band 5)

- **Main nav** (`Lobby/BottomBar_Menu`): height **180**, full width, 5 × `Menu_BottomBtn` (each `sd=(0,180)`, icons ~98–126px). **Selected** tab (`Button_03_Focus`) is **taller (189)**, icon raised (`aPos y=+34`) with a label underneath (`aPos y=-46`, **sz 34, UPPERCASE** e.g. "BATTLE").
- **Sub-tab + Back bar** (`Shop/Bottom`): height **121**; `Button_Back` **180×140** far-left; `TabButton` **257×141** each (focus variant same size, raised icon + label sz 36 Title Case e.g. "Offers"/"Daily"/"Resources").
- Notification badge on a tab: `Alert_Circle_s` **~55–58**, pinned just outside the icon's **top-right** (`aPos ≈ (48,47)`).

---

## 4. Lower-half buttons — the height law (band 4)

- The **hero primary CTA** is `Button_Tapered` / `Button_Round01` — native **455×194 / 448×195**, label **sz 88, UPPERCASE** ("PLAY"). It is **~42% screen width, centered**, *not* full-bleed.
- In `Lobby` it sits at **`aPos y=-699` from canvas center** → center ≈ **471px above the bottom edge**, i.e. its bottom edge clears the 180px nav bar by a wide margin and lands in the thumb arc.
- **Rule:** one hero CTA per screen, bottom-pinned in band 4, at the kit's y. Other screens reuse the same anchor.
- **In-dialog action buttons** (Confirm/Continue/Cancel) are smaller: `Button_124`-class **330×124** or `Button01_l` **370×160**, label **sz 42–52, Title Case** (see casing §6). Two-button dialogs split left=cancel/secondary, right=confirm/primary.

---

## 5. Standard button sizes (kit native, 1080×2340)

Circle buttons encode their diameter in the prefab name — authoritative.

| Role | Prefab | Native size | Label |
|---|---|---|---|
| **Hero CTA** | `Button_Tapered_*`, `Button_Round01_*` | **455×194 / 448×195** | sz 88, UPPERCASE |
| **Standard CTA** | `Button01_l_*` | **370×160** | sz 52, UPPERCASE default |
| **Small / inline** | `Button01_s_*` | **230×125** | sz 52 |
| **Dialog action** | `Button_124_*`, `Button_Round08_*` | **330×124 / 355×115** | sz 40–42, Title Case |
| **Floating w/ label** | `Button_Round04_*` | **158×140** | sz 36, Title Case |
| **Icon — primary** | `Button_Circle82_*` | **80×82** | — |
| **Icon — secondary** | `Button_Circle74_*` | **74×74** | — |
| **Icon — large/float** | `Button_Circle122_*`, `Circle118` | **120×122 / 117×118** | — |
| **Close / back** | `Button_Round03_*`, `Button_Round06_*` | **130×122 / 94×96** | — |
| **Sub-tab** | `Button_LeftFlush_*` / demo `TabButton` | **180×140 / 257×141** | sz 36, Title Case |
| **HUD skill** | `Button_SkillBtn_*` | **150×149** | timer sz 41.6 |
| **Tab item** | `Menu_BottomBtn` | **h 180** | sz 34 |

Min **tappable** still ≥ the kit's smallest control (~74px); pad hit area, never shrink below it. Skill buttons grouped with **spacing 15** (`Group_Button_Skill`).

---

## 6. Casing law — measured from kit text (it follows ROLE, not the prefab default)

The kit never uses the TMP `UpperCase` style flag — **casing is typed literally**, and follows what the text *is*:

| Element | Case | Kit evidence |
|---|---|---|
| Hero CTA (the big PLAY) | **UPPERCASE** | `Button_Tapered` "PLAY" sz88 |
| Selected/focus tab label | **UPPERCASE** | "BATTLE", "UPGRADE" |
| HUD utility button | **UPPERCASE** | "AUTO" |
| Section header text | **UPPERCASE** | "SHOP", "REWARDS", "SELECT A SKILL" |
| Screen / result title | **UPPERCASE** | "DEFEAT", "VICTORY" |
| Tag / badge label | **UPPERCASE** | "BONUS" |
| In-dialog action button | **Title Case** | "Confirm", "Continue" |
| Floating / nav / sub-tab label | **Title Case** | "Friends", "Offers", "Daily", "Resources" |
| Item / skill / player name | **Title Case** | "Dagger", "Dunk", "Fires laser ball" |
| Body / description / message | **Sentence case** | "Do you really want to exit the…", "Causing damage against…" |
| Numbers / timers / currency | **as-is** | "5/5", "2:45", "349,810" |

> Note: `Button01_l/_s` ship with placeholder "TEXT" in caps — ignore the placeholder, follow the **role**: a *shout* (hero CTA, header, title, tag) = UPPERCASE; a *name/command* (dialog button, nav label, item) = Title Case; *prose* = sentence case.

---

## 7. Headers, banners, ribbons — measured

### 7.1 Section header inside scroll content (`Shop`)
- `Title_Tapered` **989×67**, **left-aligned**, the **first child of each section group**, full content-width. Section-to-section vertical spacing **39**; header-to-first-card **6–19**.

### 7.2 In-popup / overlay divider header (`Play_UI_ChoiceSkill`, Result screens)
- `Title_Line01/02` **~650–735×67**, **centered**, with **flanking decorative lines** (`TitleLine_Left/Right` ~164–174 wide) and centered title text **sz 40, UPPERCASE** ("SELECT A SKILL", "REWARDS").

### 7.3 Screen / result title ribbon (`Result_Defeat/Victory`, Lobby chapter)
- `Title_Ribbon04` / `Label_Ribbon01` **690×143**, **centered, top of the screen** (`aPos y=+291`), title **sz 67, UPPERCASE**.

### 7.4 Promo banners
- **Shop:** `BannerFrame01/02` **1019 wide (94% of 1080) × 273–370**, full content-width, stacked in the scroll, featured **first**.
- **Lobby (BP-style):** `BannerFrame03` ~**1001 wide × 117**, near the **top of the hero band** (`aPos y=-115`), not among the circular floating buttons.
- **Skill-choice cards:** `BannerFrame04_Divided` **850×275**, stacked centered with **~299 pitch**, icon (`SkillFrame` 187) left, title sz54 + info sz38 right.

### 7.5 Corner ribbon / tag
- `Label_Ribbon_Red` **115×53**, pivot left, pinned to the card's **top-left** (`aPos ≈ (-261,+62)` inside the card). `Label_Tail_Red` "BONUS" tag **136×48** sits at an item's **top-center** (`aPos y=+83`). One tag per card.

---

## 8. Badges, dots, toasts (measured)

- **Alert dot** `Alert_Dot_Red` **36×39**; **number badge** `Alert_Circle_s` **55–58**. Both pin just **outside the host's top-right corner** (`aPos ≈ (+48..+57, +46..+48)` from a ~130px host center).
- **Toast** `ToastMessage_*`: **full width × 128 height** (anchor mid-stretch), text **sz 48**, demo shows it riding **~+540 / +369 / +199** above center (i.e. upper area). Colors: Gray=info, Green=success, Red=error/warning, Yellow=complete.

---

## 9. Gameplay HUD anchors (measured from `Play_UI_Action` / `Play_UI_Idle`)

| Element | Kit value | Anchor / position |
|---|---|---|
| Resource bar | h **118** | top-pin; Coin left (`aPos x=+145`), MonsterCount right (`x=-98`) |
| Combat timer | `Text_Timer` **sz 90** | top-center, `aPos y=-74` |
| Wave / stage slider | `Slider` **952×68** / `Slider_Wave` 434×65 | top-center, `aPos y=-178` |
| **Pause button** | `Button_Pause` **130×128** | bottom-left, `aPos=(95,85)` (≈95 from left, 85 from bottom) |
| **Virtual joystick** | `Joystick` **Ø356** (handle Ø125) | **bottom-center**, `aPos y=+494`; radius **178** |
| **Skill buttons** | `Group_Button_Skill`, each **150×149**, spacing 15 | bottom, `aPos y=+374`; `Button_Auto` 112×120 at `(431,373)` |
| Player HP (floating) | `Slider_Player` **67×16** | follows character, world-ish |

Center stays clear for the 3D scene — the kit keeps all controls in the bottom ~25% and info in the top ~12%.

---

## 10. Grids & lists (measured)

| Use | Prefab / container | Cell | Spacing | Pad |
|---|---|---|---|---|
| **Loot / reward grid** | `ItemFrame02_Basic` (Result) | **190×190** (icon 164 inside) | **(31,19)** | — | 4 columns, pitch 221 |
| **Equipment / stash grid** | `Equipment/Content` | **185×192** | **(25,14)** | top 30 |
| **Collection cards** | `Collection_List/Content` | **320×431** (tall card) | **(22,20)** | 38/38 |

- Reuse these cell specs; don't re-pick per screen. Loot/reward = the 190 square; inventory-style = the 185 square; showcase cards = the 320×431.

---

## 11. Popups & overlays (measured)

| Popup | Prefab | Size | Ratio | Notes |
|---|---|---|---|---|
| Small confirm | `Popup01_Basic` | **956×616** | 88% × 26% | centered; Close **94×96** top-right `aPos=(-64,-68)`; Confirm **410×162** bottom |
| Settings | `Popup08_Topbar_Divided` | **978×1288** | 90% × 55% | centered, scrollable body |
| Leaderboard | `Popup07_Topbar_Divided_Scroll` | **978×1577** | 90% × 67% | sub-tabs `TabButton` 409×114 |
| Warning (full dim) | `PopupDim_Warning` | full-screen dim | — | big message sz 80, no card |

- Popup width ≈ **90% (956–978)**, centered; close (X) **top-right inset ~64**; primary action button bottom-center.

---

## 12. Text alignment & type sizes (measured)

- **Top-bar / screen / result titles:** centered. **Section headers (Tapered):** left. **Stat/value rows:** value right-aligned (`align=Right` on item counts). **Body/desc:** left. **Resource numbers:** center.
- **Kit type sizes seen** (heavier than the guidelines' scale — the kit shouts louder): hero CTA **88**, combat timer **90**, screen/result title **67**, top-bar title **56**, `Button01` label **52**, skill title **54**, divider header / sub-title **40**, dialog button / info **42**, nav & floating labels **36**, resource number **36–40**, badge number **34**, tag **29**.

---

## 13. Multi-resolution anchoring (how the kit pins)

| Element | Kit anchor |
|---|---|
| Resource bar, HUD top strip | top-stretch (`aMin=(0,1) aMax=(1,1)`) |
| Bottom bar / nav | bottom-stretch (`aMin=(0,0) aMax=(1,0)`) |
| Hero CTA, dialog buttons | center or bottom-pin (`aMin=aMax=(0.5,…)`) |
| Floating buttons | corner-pin (`aMin=aMax=(0,1)` or `(1,1)`) |
| Toast | mid-stretch (`aMin=(0,0.5) aMax=(1,0.5)`) |
| Grids/scroll content | top-stretch content, pivot top |

Match the kit's anchor preset per element; it's already authored for single-axis stretch.

---

## 14. Hard rules (placement)

1. **Match the kit prefab's own size/anchor/casing** — the kit is the standard; don't eyeball or re-scale.
2. Build from the **five-band spine** (§1); chrome edge-pinned, never centered.
3. **One hero CTA per screen** in band 4, kit casing UPPERCASE.
4. **Casing follows role** (§6): shout=CAPS, name=Title, prose=sentence.
5. Section headers **left** + Tapered; titles/results **centered** + Ribbon; dividers **centered + flanking lines**.
6. Grids/lists reuse the §10 cells; banners full-content-width & featured-first (§7.4); one corner tag per card.
7. Verify worldPos on-screen + an F8 shot before "done" (see `ui-placement` skill).

---

## 15. Decision log

- **2026-06-14 — Canvas reference RATIFIED:** kit-based screens use the kit's **1080×2340 (Match 0.487)** CanvasScaler reference. All measured px in this doc apply **1:1**. The older 1440×2560 (16:9) spec is superseded for kit screens. (If a non-kit/legacy canvas must stay 1440×2560, use the listed ratios.)

---

> When a placement number changes, update **this file** (it is the measured standard) — not the per-screen mockups.
