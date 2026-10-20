# Quality of offline 3D models

- Check the actual Android render of every added or changed model, including a rotated view. Geometry loading successfully is not sufficient visual validation.
- Keep the model distinct from its background and preserve visible surface relief. Avoid accidental white/neutral default surfaces and crushed near-black bodies. A genuine light finish needs an explicit explanation and a contrasting presentation.
- For an uncoloured source, choose a readable matte illustrative material and label the colour as conditional in Russian. Do not claim it reproduces authentic paint.
- Preserve source credits, licences, variant identity and geometry when changing display materials. Record `displayColorMode` as `source` or `illustrative` in `models.json`.
- Keep newly researched models in the separate collection until the user asks to integrate that batch. Changes to existing model presentation do not automatically add collected models.
- Read `OFFLINE_3D.md` for model attribution, card mapping and the visual review policy.
