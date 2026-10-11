# Character Prompts

All characters are **original**. Use the STYLE BLOCK from `01_style_bible.md` before each prompt.
Workflow: generate concept art with these prompts, pick one, then sculpt/model it in Blender using the concept as a reference (see GUIDE Phase 4).

For consistency, always generate a **turnaround sheet** first, then an **expression sheet**, then lock the design.

---

## 1. Pip (lead, about 6 years old)
Curious, cheerful, a bit messy, learns every habit through trying it.

**Concept prompt**
```
[STYLE BLOCK], a cheerful 6-year-old child named Pip, warm medium-brown skin, big round dark brown eyes,
short curly hair with a small cowlick, wide gap-toothed smile, wearing a sunny-yellow t-shirt, teal dungarees
and red sneakers, head slightly large for the body, relaxed A-pose
```
**Turnaround prompt**
```
character turnaround sheet, same character shown front view, three-quarter view, side view and back view,
consistent design, [Pip description], plain light-grey background, even lighting
```
**Expression sheet prompt**
```
character expression sheet, [Pip description], 9 expressions in a grid: happy, sad, surprised, sleepy,
proud, curious, silly, determined, giggling, plain light-grey background
```

## 2. Zuri (best friend, about 6 years old)
Confident, loves to count and sing, shows the right way to do things.
```
[STYLE BLOCK], a confident 6-year-old girl named Zuri, deep brown skin, two high puffs of dark hair tied with
purple ribbons, bright smile, wearing a purple hoodie vest over a white t-shirt, green shorts and white shoes,
big sparkling eyes, A-pose
```

## 3. Tomo (younger sibling, about 3 years old)
Tiny, copies everything, perfect for "oops, let's try again" moments.
```
[STYLE BLOCK], an adorable 3-year-old toddler named Tomo, light olive skin, round cheeks, a few wisps of
straight black hair, big curious eyes, wearing a mint-green romper with a small star patch, chubby proportions,
head about 40% of body height, A-pose
```

## 4. Nana Rue (grown-up, can be read as parent, grandparent or carer)
Calm, kind, never scolds; explains with a smile.
```
[STYLE BLOCK], a gentle grown-up named Nana Rue, warm tan skin, soft laugh lines, silver-white curly hair in a
loose bun, round glasses, wearing a soft coral cardigan over a cream top and comfortable trousers, kind eyes,
relaxed standing pose
```

## 5. Biscuit (pet companion, no specific species)
Round fluffy creature that reacts with sounds, no dialogue; gives comic relief.
```
[STYLE BLOCK], a small round fluffy creature named Biscuit, cream and caramel fur, floppy ears, tiny stubby
legs, big shiny black eyes, a little curly tail, ambiguous species between a puppy and a plush toy, soft and
huggable, cute, 3/4 view
```

## 6. Pop-up helpers (props with faces, for habit explanations)
Short, optional, great for teeth, hands and sleep.
```
[STYLE BLOCK], a friendly cartoon toothbrush character with a smiling face, big eyes, tiny arms and legs,
mint-green handle, soft bristles, sparkles around it, product-style render, no text
```
```
[STYLE BLOCK], a cute soap bubble character with a happy face, translucent shiny iridescent sphere,
tiny sparkles, floating, sky-blue background
```
```
[STYLE BLOCK], a sleepy crescent-moon character with a calm smiling face wearing a tiny nightcap, glowing
soft yellow, gentle stars around it
```

---

## Character sheet for Blender (give this to your modeling step)
For each character record: height in head-units, 3 main colors (hex), hair type, signature item, voice type, walk style. Example:

| Field | Pip |
|---|---|
| Height | 4.5 heads |
| Colors | #F7C631 shirt, #1E8F8F dungarees, #D93B2B shoes |
| Signature | cowlick + gap-toothed grin |
| Voice | bright child voice (Kokoro `af_nicole`, pitch up slightly) |
| Walk | bouncy, slightly pigeon-toed |

## Tools for turning concepts into 3D (all free options)
- **Blender sculpt + box modeling** (best control, recommended; follow the Blender Studio character workflow tutorials).
- **Reference rigs under CC-BY** from Blender Studio (Rain, Snow, Sprite and others) to learn how pro rigs are built, or to kit-bash. Credit text is required, see `assets/LICENSES.csv`.
- **Image-to-3D** (TripoSR, MIT licensed, runs locally) can give a base mesh from your concept art; expect to retopologize and clean it up in Blender. Verify the license of any model before use.
