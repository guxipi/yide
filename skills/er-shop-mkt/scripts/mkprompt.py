"""Write codex image_gen prompt files for ER shop MKT visuals from a jobs JSON.

usage: py -3 mkprompt.py jobs.json OUT_DIR
jobs.json = [{"name": "card_vesper", "kind": "card"|"kv"|"object"|"cut"|"plate", ...fields per kind...}, ...]
  cut:   {"src": approved image, "keep": "the man (whole body, hair, ...) AND the crate he holds", "rest": "sky, floor, ...", "px": "1672x941"}
  plate: {"src": approved image, "remove": "the woman", "fill": "the ship bridge interior and the window"}
Writes OUT_DIR/p_<name>.txt; images will be saved by codex to OUT_DIR/img/<name>.png.

Templates are the W4 v3b/v4 prompts that passed review on 2026-10-27; edit fields, not the template text.
"""
import json, os, sys

VAULT = os.environ.get('ER_VAULT', 'I:/My Drive/Obsidian/ExtractionRaider/01 - 星际拓荒重构')
ART = VAULT + '/013 美术'
V4_ICON = VAULT + '/011_基地星/art/基地星icon_v4_style_reference.png'
STYLE_KV = [ART + '/KeyVisual/Social/ER_YouTube横幅_补给舱拔河_无logo_2560x1440_2026-10-09.png',
            ART + '/KeyVisual/ExtractionBattle/ER_ExtractionBattle_云海邀请_1672x941_2026-10-08.png']
B = ART + '/角色手册/img/'
BIBLE = {  # finalized sheets only (er-character-sheet-ssot); verified md5 against W4 refs 2026-10-27
    'Rook':   [B + 'expedition_主角定稿_全身与俯视_1672x941.png', B + 'expedition_主角定稿_正脸微笑与无表情_1672x941.png'],
    'Vesper': [B + 'expedition_Vesper当前造型_1024x1536.png', B + 'expedition_Vesper真人动作六格_1024x1536.png'],
    'Coda':   [B + 'expedition_人物设计板Coda_A版v6_1672x941.png', B + 'expedition_Coda表情表_1672x941.png'],
    'Wren':   [B + 'expedition_人物设计板Wren_活力版B_v2_1672x941.png', B + 'expedition_Wren表情表_1672x941.png'],
    'Tuba':   [B + 'expedition_人物设计板Tuba方向A_1672x941.png', B + 'expedition_Tuba表情表_1672x941.png'],
    'Harrow': [B + 'expedition_人物设计板Harrow方向A_1672x941.png', B + 'expedition_Harrow表情表_1672x941.png'],
}
SIZE = {'portrait': 'portrait 1024x1536', 'landscape': 'landscape 1672x941', 'grid': 'landscape 1536x1024'}

def head(refs, out, size):
    return ("Do not read or load any skill. Call image_gen with referenced_image_paths set to EXACTLY "
            + json.dumps(refs, ensure_ascii=False) + " and pass the instructions below to image_gen verbatim.\n\n"
            f"Use the built-in image_gen tool (not a CLI fallback). Generate ONE NEW image, {size}, quality high. "
            f"Save it to ./img/{out}.png, then report the real pixel size. Do not touch any other file.\n\n")

KVSTY = ("Images 1 and 2 are STYLE REFERENCES ONLY: copy their rendering (large flat colour areas, simple two-tone shading with crisp "
         "light/shadow edges, cool blue-violet shadows, no black outlines, minimal surface texture). Do NOT copy their content, people, "
         "layout, time of day, weather or lighting.")
AVOID = ("AVOID: black outlines, realistic material texture, skin pores, fabric noise, brush noise, photographic lighting, lens blur, "
         "text, logos, UI, extra characters, extra limbs. Count arms and hands: exactly two arms and two hands per character.")

# template A: character key art (popup header, BP header, 7-day / growth fund head)
KV = ("WHAT THIS IS: key art for {what} in our mobile game shop. Character, props and background must look like ONE painting with the same light and colour.\n\n"
      "REFERENCES: " + KVSTY + " Images 3 and 4 are the character bible of {name}: reproduce EXACTLY this character ({keep}). Do not invent or change any feature.\n\n"
      "STORY: {story}\n\nCOMPOSITION: {comp}\n\nTIME AND LIGHT: {light}\n\n" + AVOID)

# template C: horizontal top-up card face (monthly card, ad-free, lifetime)
CARD = ("WHAT THIS IS: the printed face of a horizontal prepaid gift card for our mobile game shop ({what}). Character, props and background must look like ONE painting with the same light and colour.\n\n"
        "REFERENCES: " + KVSTY + " Images 3 and 4 are the character bible of {name}: reproduce EXACTLY this character ({keep}). Do not invent or change any feature.\n\n"
        "STORY: {story}\n\n"
        "COMPOSITION: landscape, like a credit card face. {name} in the LEFT 55%, framed from the waist up, slightly low camera, head near the top edge with a little headroom, "
        "turned three-quarter toward image right. The RIGHT 40% is a calm simple {bg} gradient with only a few soft shapes, because big UI text goes there. "
        "Background behind the character is a simple {bg} backdrop with a large soft sunburst, like a premium card print, not a detailed scene.\n\n"
        "TIME AND LIGHT: studio card print. Key light warm from upper left, cool violet ambient, a soft pale rim light on the right edge of the character; shadows cool blue-violet, never black.\n\n" + AVOID)

# template B: objects / packaging in er-icon-gen v4 style (packs, point cards, task icon grids)
ICON = ("The provided reference image is the STYLE reference: match its exact art style (palette, outline weight, gloss, shading): "
        "thick clean dark outline, soft inner shading, vibrant highly-saturated super-casual mobile-game icon rendering. "
        "IGNORE its blue frames, its grid layout and its objects; draw only what is described below.\n\n"
        "{desc}\n\n"
        "Flat even lighting. Absolutely NO glow, NO sparkles, NO stars, NO particles, NO rim light, NO lens flare, NO motion blur, NO drop shadow.\n"
        "PHONE READABILITY (very important): it must read instantly at 64 px on a phone. One bold main silhouette, at most two or three "
        "large secondary parts, big flat color areas. NO fine patterns, NO mesh or grid textures, NO circuit lines, NO tiny screws, bolts "
        "or rivets, NO small engraved details.\n"
        "ABSOLUTELY NO TEXT ANYWHERE: no letters, numbers, logos, glyphs or fake writing. Blank areas stay plain single-color surfaces.\n"
        "Background: one flat solid pure green #00FF00, no gradient, no floor, no frame.")
PACK = ("OBJECT: a sealed booster card pack, front view, upright, filling about 85% of the image height with clean margin. "
        "A puffy foil wrapper with zigzag crimped seals along the top and bottom edges, and a small round hang hole punched in the top seal. "
        "Front face: {base} background printed with a bold sunburst of {rays} rays radiating from the exact center of the face, big simple wedges, "
        "plus one wide plain {band} band across the lower fifth of the face left blank for a name. The center of the face has no object on it.")

# template D: edits of an approved image (same file is the only reference, so the edit keeps identity)
EDIT_HEAD = ("Use the built-in image_gen tool (not a CLI fallback) to EDIT the attached image. One image_gen call. Keep the exact same size ({size}), "
             "framing and composition. Save the result to ./img/{out}.png, then report the real pixel size. Do not touch any other file.\n\n")
CUT = ("Keep {keep} EXACTLY as they are, pixel for pixel, same position and size. Replace EVERYTHING else ({rest}) with one flat solid pure green "
       "colour #00FF00, no gradient, no shadow, no glow, no rim of the old background around them. Hair edges stay clean. Nothing else changes.")
PLATE = ("Remove {remove} completely (including the shadow cast). Fill the area by naturally continuing {fill} exactly as it continues around, "
         "in the same painting style and the same lighting. Everything else stays pixel identical. No new characters, no text.")

BANNED = ['holographic', 'glossy', 'chrome', 'specular', 'foil shimmer', 'iridescent', 'metallic sheen', 'impasto', 'brushstroke', 'realistic', 'photoreal']

def allow_text(body, job):
    """job['text'] = the only words allowed in the picture (e.g. "30", "AD"); STORY must name them and say they stay complete."""
    if not job.get('text'):
        return body
    if job['text'] not in job.get('story', ''):
        sys.exit(f"{job['name']}: STORY must name the allowed text {job['text']!r} and say it stays complete and unobstructed")
    return body.replace('lens blur, text, logos, UI,', 'lens blur, logos, UI, any writing other than the exact text named in STORY,')

def build(job):
    k, n = job['kind'], job['name']
    if k == 'object':
        desc = PACK.format(**job['pack']) if 'pack' in job else job['desc']
        low = desc.lower()
        bad = [w for w in BANNED if w in low]
        if bad:
            sys.exit(f"{n}: material/style words not allowed in object prompts: {bad}")
        return head([V4_ICON], n, SIZE[job.get('size', 'portrait')]) + ICON.format(desc=desc)
    if k in ('cut', 'plate'):
        src = os.path.abspath(job['src']).replace(chr(92), '/')
        body = CUT.format(**job) if k == 'cut' else PLATE.format(**job)
        return ("Do not read or load any skill. Call image_gen with referenced_image_paths set to EXACTLY " + json.dumps([src], ensure_ascii=False)
                + " and pass the instructions below to image_gen verbatim.\n\n" + EDIT_HEAD.format(size=job.get('px', '1672x941'), out=n) + body)
    refs = STYLE_KV + BIBLE[job['hero']]
    f = dict(job, name=job['hero'])
    f.setdefault('keep', 'face, hair, outfit, colours and accessories exactly as in the bible')
    if k == 'card':
        body = CARD.format(**f)
        if job.get('prop'):  # the product must read at a glance: key prop centred, ~45% card height, overlapping the hero
            body = body.replace('not a detailed scene.', 'not a detailed scene. ' + job['prop'] + ' This key prop sits near the centre of the card, about 45% of the card height, overlapping the character.')
        return head(refs, n, SIZE['landscape']) + allow_text(body, job)
    if k == 'kv':
        if not job.get('light'):
            sys.exit(f"{n}: kv jobs must state TIME AND LIGHT ('light') from the story")
        return head(refs, n, SIZE[job.get('size', 'landscape')]) + allow_text(KV.format(**f), job)
    sys.exit(f"{n}: unknown kind {k}")

if __name__ == '__main__':
    jobs = json.load(open(sys.argv[1], encoding='utf-8'))
    out = sys.argv[2]
    os.makedirs(out + '/img', exist_ok=True)
    for j in jobs:
        need = {'object': [V4_ICON], 'cut': [j.get('src', '')], 'plate': [j.get('src', '')]}.get(j['kind'], STYLE_KV + BIBLE.get(j.get('hero'), []))
        for r in need:
            if not os.path.exists(r):
                sys.exit(f"missing reference: {r}")
        text = build(j)  # build first so a rejected job leaves no empty prompt file behind
        open(f"{out}/p_{j['name']}.txt", 'w', encoding='utf-8').write(text + "\n")
        print('wrote', f"{out}/p_{j['name']}.txt")
