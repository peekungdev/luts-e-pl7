# Fujifilm Classic Chrome LUTs for RapidRAW (Olympus PEN E-PL7)

Six 3D LUTs (`.cube`, 33×33×33) that give raw files in [RapidRAW](https://github.com/CyberTimon/RapidRAW) the look of Fujifilm's **Classic Chrome** film simulation. Four variants add Fuji's **Color Chrome Effect** and **Color Chrome FX Blue** settings, and two apply those effects on their own. They were made for, and checked on, raw files from an Olympus PEN E-PL7.

| File | What it does |
|---|---|
| `Fuji Classic Chrome (E-PL7).cube` | Classic Chrome on its own |
| `Fuji Classic Chrome + Color Chrome Weak (E-PL7).cube` | Classic Chrome with Color Chrome Effect *Weak* |
| `Fuji Classic Chrome + Color Chrome Strong (E-PL7).cube` | Classic Chrome with Color Chrome Effect *Strong* |
| `Fuji Classic Chrome + Color Chrome Strong + FX Blue Strong (E-PL7).cube` | The above, plus Color Chrome FX Blue *Strong* |
| `Fuji Color Chrome Effect Strong (E-PL7).cube` | Color Chrome Effect *Strong* only, colours otherwise unchanged |
| `Fuji Color Chrome FX Blue Strong (E-PL7).cube` | Color Chrome FX Blue *Strong* only |

## Install

Copy the files from [`luts/`](luts) into RapidRAW's LUT folder. They then appear in the editor's LUT list.

| OS | Folder |
|---|---|
| Windows | `%APPDATA%\io.github.CyberTimon.RapidRAW\luts` |
| macOS | `~/Library/Application Support/io.github.CyberTimon.RapidRAW/luts` |
| Linux | `~/.local/share/io.github.CyberTimon.RapidRAW/luts` |

## Use

1. Open a raw file and keep RapidRAW's **AgX** tone mapper, which is its default for raw files. The LUTs are built for AgX. On the *Basic* tone mapper they still work, but less accurately.
2. Pick a LUT. Set exposure and white balance as usual. You don't need to flatten contrast first, because the LUT already accounts for AgX.
3. Use the LUT intensity slider to blend the look back with the plain AgX rendering.

Classic Chrome is darker and lower in saturation than RapidRAW's default rendering, with firmer shadows. That is the intended look.

## How they were made

RapidRAW applies user LUTs to the finished sRGB image, after the AgX tone mapper. Measured film-simulation tables expect a flat, neutral raw rendering instead. Applying one directly therefore stacks two tone curves and gives a washed-out result. These LUTs avoid that by undoing RapidRAW's AgX transform first:

```
lut(x) = ClassicChrome( sRGB( shoulder( AgX⁻¹(x) ) ) )
```

In short, each LUT swaps RapidRAW's rendering for a Classic Chrome rendering of the same scene data. `shoulder` gives a soft highlight roll-off, so bright areas keep a gradient instead of clipping hard.

- **Classic Chrome** comes from measured data: Stuart Sowerby's fit of Fujifilm X-Trans III cameras, taken from the HaldCLUT collection in [cedeber/hald-clut](https://github.com/cedeber/hald-clut).
- **Color Chrome Effect and FX Blue** are modelled, not measured. Following Fujifilm's description, they deepen highly saturated colours while keeping their chroma, so vivid subjects keep their tonal gradation. The main effect covers reds through greens; FX Blue covers blues. The strengths are a judgement call.

## Accuracy

RapidRAW 1.6.9's AgX pipeline was re-implemented in Python, and nine E-PL7 raw files were rendered through it. On those files, the Classic Chrome LUT matched the measured Classic Chrome table (applied to a flat rendering of the same file) to **0.3–0.5/255 mean error** per file. The 99th percentile was about 1/255 on eight files and 6/255 on the ninth. The LUTs have not been compared pixel-for-pixel inside the RapidRAW app itself.

The table does not depend on the camera. RapidRAW converts each camera's colour to a common space before the LUT stage, so "E-PL7" means *checked on E-PL7 files*, not *tuned only for the E-PL7*. The LUTs should behave the same on raw files from other cameras.

## Rebuilding

[`tools/`](tools) contains the scripts that produced the LUTs. You need Python 3 with `numpy` and `pillow`; `preview.py` also needs `rawpy`.

1. Download `HaldCLUT/Fujifilm XTrans III/Fuji XTrans III - Classic Chrome.png` from [cedeber/hald-clut](https://github.com/cedeber/hald-clut) and save it as `ref/Classic_Chrome.png`.
2. Build:
   ```
   python tools/build.py ref out 33 E-PL7 "Olympus PEN E-PL7"
   ```
3. Optionally, render raws through the simulated RapidRAW pipeline. This writes contact sheets and reports the error against the reference:
   ```
   python tools/preview.py ref out previews E-PL7 photo1.ORF photo2.ORF
   ```

## Licence and credits

- The Classic Chrome data is derived from Stuart Sowerby's Fuji film simulation profiles ([sowerby.me](https://blog.sowerby.me/fuji-film-simulation-profiles/)), as distributed in [cedeber/hald-clut](https://github.com/cedeber/hald-clut) under GPL-3.0. These LUTs and scripts are therefore released under the [GNU GPL v3.0](LICENSE).
- Not affiliated with or endorsed by Fujifilm, OM Digital Solutions or Olympus. Classic Chrome and Color Chrome are Fujifilm's names for their film simulations.
