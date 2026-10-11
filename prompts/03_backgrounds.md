# Background and Set Prompts

Use these for concept art first, then build the sets in Blender as **modular low-poly scenes with painted textures** (cheap to render, looks storybook-polished).

Prefix with a short style line:
```
STYLE: stylized 3D animated children's film environment, soft rounded shapes, warm soft lighting, hand-painted
textures, cozy and tidy, saturated friendly colors, no text, no people, wide establishing shot
```

## Core sets (build these first; they cover most habit episodes)

### 1. Pip's bedroom (morning)
```
STYLE, a cozy child's bedroom in morning sunlight, a small bed with a patchwork quilt, a window with
sheer curtains and blue sky, a bookshelf with colorful toy blocks, a round rug, a few plush toys, warm wooden
floor, gentle dust motes in sunbeams
```
### 2. Pip's bedroom (night)
```
STYLE, the same child's bedroom at night, soft warm bedside lamp glow, window showing a calm blue night sky
with a crescent moon and stars, quilt turned down, a stack of picture books, very cozy and safe, soft shadows
```
### 3. Bathroom
```
STYLE, a bright child-friendly bathroom, a step stool in front of a low sink, a round mirror, a cup with
colorful toothbrushes, soap bubbles floating, soft aqua tiles, fluffy towels, sparkling clean
```
### 4. Kitchen and dining table
```
STYLE, a warm family kitchen, a wooden table with a bowl of colorful fruit and vegetables, a window with
herbs on the sill, bright morning light, simple cabinets, cheerful and uncluttered
```
### 5. Playroom (tidying toys)
```
STYLE, a sunny playroom with toy boxes in primary colors, scattered building blocks and soft toys on the floor,
a rug with road pattern, shelves with labeled-by-color baskets (no text), big window
```
### 6. Front garden and street (walking, road safety)
```
STYLE, a friendly neighborhood front garden with flowers and a small gate, a quiet street with a zebra crossing,
tall friendly trees, blue sky with soft clouds, no cars close up, gentle golden light
```
### 7. Park (sharing, playing)
```
STYLE, a sunny park with a gentle hill, a small playground with a slide and swings, a pond with ducks,
flowering bushes, picnic blanket, wide open space for characters to play
```
### 8. Magic "habit world" interlude (for songs and explainers)
```
STYLE, a dreamy abstract world of soft pastel clouds, floating sparkles and rounded rainbow arches, gentle
gradients, whimsical and calm, good for a song sequence
```

## Building these in Blender (cost-saving rules)
1. Build with simple primitives and bevels, then add painted textures (Blender texture paint, or generated concept art projected as textures).
2. Reuse one **kit** of pieces (walls, windows, doors, tables, beds, rugs) across all sets; change colors and dressing, not geometry.
3. Use the same four or five props in every episode (toothbrush, soap, cup, bed, plush toy).
4. Free CC0 assets help: Poly Haven (HDRIs, textures, models), Kenney assets. Log each one in `assets/LICENSES.csv`.
5. Keep polygons light and light counts low; Eevee renders a full 1080p frame in seconds on a modest GPU.

## Camera angles (per set)
Create 3 saved cameras per set: **Wide**, **Medium**, **Close**. Re-use them in every episode.
