# Fujifilm Classic Chrome for RapidRAW, Lightroom and Capture One (Olympus PEN E-PL7)

These files give raw photos the look of Fujifilm's **Classic Chrome** film simulation. Variants also add Fuji's **Color Chrome Effect** and **Color Chrome FX Blue**. They were made for, and checked on, raw files from an Olympus PEN E-PL7, and come in three versions:

| App | Download | What you get |
|---|---|---|
| **RapidRAW** | `luts-e-pl7-v1.1.0-rapidraw-cube.zip` | 6 LUTs (`.cube`) |
| **Adobe Lightroom / Lightroom Classic / Camera Raw** | `luts-e-pl7-v1.1.0-lightroom-xmp.zip` | 6 profiles (`.xmp`) |
| **Capture One** | `luts-e-pl7-v1.1.0-captureone-costyle.zip` | 1 style (`.costyle`), Classic Chrome only |

Download them from the [latest release](../../releases/latest), or take the files from [`luts/`](luts), [`lightroom/`](lightroom) and [`captureone/`](captureone).

The six looks in the RapidRAW and Lightroom versions:

| Name | What it does |
|---|---|
| Fuji Classic Chrome (E-PL7) | Classic Chrome on its own |
| Fuji Classic Chrome + Color Chrome Weak (E-PL7) | Classic Chrome with Color Chrome Effect *Weak* |
| Fuji Classic Chrome + Color Chrome Strong (E-PL7) | Classic Chrome with Color Chrome Effect *Strong* |
| Fuji Classic Chrome + Color Chrome Strong + FX Blue Strong (E-PL7) | The above, plus Color Chrome FX Blue *Strong* |
| Fuji Color Chrome Effect Strong (E-PL7) | Color Chrome Effect *Strong* only, colours otherwise unchanged |
| Fuji Color Chrome FX Blue Strong (E-PL7) | Color Chrome FX Blue *Strong* only |

Classic Chrome is lower in saturation than a standard rendering, with firmer shadows and muted colours. That is the intended look.

## RapidRAW

Copy the six `.cube` files into RapidRAW's LUT folder. They then appear in the editor's LUT list.

| OS | Folder |
|---|---|
| Windows | `%APPDATA%\io.github.CyberTimon.RapidRAW\luts` |
| macOS | `~/Library/Application Support/io.github.CyberTimon.RapidRAW/luts` |
| Linux | `~/.local/share/io.github.CyberTimon.RapidRAW/luts` |

Keep RapidRAW's **AgX** tone mapper, which is its default for raw files. The LUTs are built for it. Pick a LUT, set exposure and white balance as usual, and use the LUT intensity slider to blend the look back with the plain rendering.

## Lightroom and Camera Raw

The `.xmp` files are Camera Raw profiles, which Lightroom calls "creative profiles". They need no Photoshop and no conversion.

1. Import them:
   - **Lightroom Classic:** *File › Import Develop Profiles and Presets…*, then select the six `.xmp` files.
   - **Lightroom** (the cloud-based app): *File › Import Profiles & Presets…*
   - **Camera Raw:** the Presets panel's *…* menu › *Import Profiles & Presets…*
   - Or copy them into the Camera Raw settings folder and restart: `%APPDATA%\Adobe\CameraRaw\Settings` on Windows, `~/Library/Application Support/Adobe/CameraRaw/Settings` on macOS.
2. In Develop, open the **Profile Browser** (the grid icon next to *Profile* in the Basic panel). The looks are in the group **Fuji Classic Chrome (E-PL7)**.
3. Each profile has an **Amount** slider (0–200). It starts at 100, which is the calibrated strength.

The profiles are calibrated against Adobe's own rendering, so they keep your photo's brightness and add only the Classic Chrome look. They work on raw files from any camera, and on JPEGs.

## Capture One

Capture One can't load LUTs or Lightroom profiles. The Capture One version is therefore a **style** that rebuilds Classic Chrome from Capture One's own tools: red, green and blue curves plus a Saturation setting.

1. Import `Fuji Classic Chrome (E-PL7).costyle` with Capture One's **Import Styles** command. Or copy it into the user styles folder: `%LOCALAPPDATA%\CaptureOne\Styles50` on Windows, `~/Library/Application Support/Capture One/Styles` on macOS.
2. Apply it from *Styles and Presets › User Styles*. Leave *Base Characteristics › Curve* at its default.

A style can't do everything a LUT can:

- **Only Classic Chrome itself is available.** The Color Chrome effects change specific hues, which curves and one saturation slider can't express.
- **It is less exact than the other versions.** In testing it got about three times closer to Classic Chrome than no look at all. It still came out slightly more colourful than the LUT version. If it looks too vivid, lower Saturation a little more.

## Other photo editors

The `.cube` files are standard 3D LUTs (sRGB in, sRGB out), so other editors can use them too:

- **Photoshop:** *Layer › New Adjustment Layer › Color Lookup*, then *3DLUT File › Load 3D LUT…*
- **Affinity Photo:** a LUT adjustment layer.
- **darktable:** the *lut 3D* module (set the LUT folder in *Preferences › Processing* first).
- **DaVinci Resolve**, and other editors with `.cube` support.

The `.cube` files are calibrated for RapidRAW, so elsewhere they are an approximation. On a typical default rendering, full strength comes out slightly darker than true Classic Chrome. Start at **60–70% strength** and adjust by eye. For Lightroom and Camera Raw, use the `.xmp` profiles instead.

## How they were made

Every version applies Classic Chrome **on top of the editor's own finished image**. A measured film-simulation table expects a flat, neutral raw rendering instead. Applied directly, it stacks a second tone curve on top of the editor's and comes out wrong. Each version therefore first undoes its host's rendering, then applies Classic Chrome to the result:

```text
look(x) = ClassicChrome( sRGB( shoulder( k · Host⁻¹(x) ) ) )
```

- **RapidRAW:** `Host` is RapidRAW 1.6.9's AgX tone mapper, re-implemented from its shader source. `k` is 1.
- **Lightroom:** `Host` is Adobe's default rendering, re-implemented from Adobe's DNG SDK 1.7.1: the ACR3 tone curve applied in ProPhoto RGB with Adobe's hue-preserving method. The SDK shows that Camera Raw applies a profile's table right after this tone curve. Adobe's rendering puts mid-grey about ⅔ stop brighter than AgX, so `k` (+0.68 EV) matches the two at mid-grey, and the profiles don't darken the photo. Each table is stored as a 32×32×32 RGB table in the exact format the SDK reads and writes.
- **Capture One:** the curves are read off the Lightroom look's grey axis, and the Saturation value is fitted to its colours. Capture One's default film curve is a contrasty rendering, much like Adobe's.

`shoulder` gives a soft highlight roll-off, so bright areas keep a gradient instead of clipping hard.

- **Classic Chrome** comes from measured data: Stuart Sowerby's fit of Fujifilm X-Trans III cameras, taken from the HaldCLUT collection in [cedeber/hald-clut](https://github.com/cedeber/hald-clut).
- **Color Chrome Effect and FX Blue** are modelled, not measured. Following Fujifilm's description, they deepen highly saturated colours while keeping their chroma, so vivid subjects keep their tonal gradation. The main effect covers reds through greens; FX Blue covers blues. The strengths are a judgement call.

## Accuracy

The table compares each version with the measured Classic Chrome table applied to a flat rendering of the same file. The test used nine E-PL7 raw files, rendered through Python re-implementations of each host's pipeline. Lower is better.

| Version | Simulated host | Mean error |
|---|---|---|
| RapidRAW `.cube` | RapidRAW 1.6.9 AgX | 0.3–0.5 / 255 |
| Lightroom `.xmp` | Adobe default rendering (DNG SDK) | 0.4 / 255 |
| Capture One `.costyle` | Adobe default rendering, standing in for Capture One's | 1.9 / 255 |
| *No look at all* | Adobe default rendering | *5.6 / 255* |
| *RapidRAW `.cube` loaded in Lightroom* | Adobe default rendering | *7.2 / 255* |

None of the three has been checked pixel-for-pixel inside the real app:

- **Lightroom:** it may use *Adobe Color* rather than the SDK's default rendering, and Lightroom's processing differs in details, so expect small differences there.
- **Capture One:** its style keys come from published `.costyle` files, and its exact Saturation scale isn't documented.

The looks don't depend on the camera. "E-PL7" means *checked on E-PL7 files*, not *tuned only for the E-PL7*.

## Rebuilding

[`tools/`](tools) contains the scripts that produced every file. You need Python 3 with `numpy` and `pillow`; `preview.py` also needs `rawpy`.

1. Download `HaldCLUT/Fujifilm XTrans III/Fuji XTrans III - Classic Chrome.png` from [cedeber/hald-clut](https://github.com/cedeber/hald-clut) and save it as `ref/Classic_Chrome.png`.
2. For the Lightroom and Capture One versions, get Adobe's [DNG SDK](https://helpx.adobe.com/camera-raw/digital-negative.html). The scripts read Adobe's tone curve from its `dng_sdk/source/dng_render.cpp`, so no Adobe code is copied into this repository.
3. Build:

   ```sh
   python tools/build.py ref out 33 E-PL7 "Olympus PEN E-PL7"
   python tools/build_lightroom.py ref path/to/dng_render.cpp lightroom E-PL7
   python tools/build_captureone.py ref path/to/dng_render.cpp captureone E-PL7
   ```

4. Optionally, render raws through the simulated RapidRAW pipeline. This writes contact sheets and reports the error against the reference:

   ```sh
   python tools/preview.py ref out previews E-PL7 photo1.ORF photo2.ORF
   ```

## Licence and credits

- The Classic Chrome data is derived from Stuart Sowerby's Fuji film simulation profiles ([sowerby.me](https://blog.sowerby.me/fuji-film-simulation-profiles/)), as distributed in [cedeber/hald-clut](https://github.com/cedeber/hald-clut) under GPL-3.0. These files and scripts are therefore released under the [GNU GPL v3.0](LICENSE).
- The Lightroom profile format and Adobe's rendering were re-implemented from Adobe's DNG SDK. The Capture One style format follows the published styles in [lolochristen/CaptureOne_FilmStyles](https://github.com/lolochristen/CaptureOne_FilmStyles).
- Not affiliated with or endorsed by Fujifilm, OM Digital Solutions, Olympus, Adobe or Capture One. Classic Chrome and Color Chrome are Fujifilm's names for their film simulations. Lightroom, Photoshop and Camera Raw are Adobe trademarks. Capture One is a trademark of Capture One A/S.
