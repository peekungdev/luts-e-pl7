"""Preview / calibration on real E-PL3 raws.

Usage: preview.py <ref_dir> <lut_dir> <out_dir> <camera label> <raw> [<raw> ...]
Renders each raw the way RapidRAW does (AgX), applies the LUTs, writes a
contact sheet, and reports how the result compares with the measured Classic
Chrome table applied to a flat render of the same file.
"""
import sys, os
import numpy as np
import rawpy
from PIL import Image, ImageDraw
import lutlib as L

ref, lut_dir, out_dir, cam, raws = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
CC_FULL = L.load_hald(f"{ref}/Classic_Chrome.png")
names = [
    f"Fuji Classic Chrome ({cam})",
    f"Fuji Classic Chrome + Color Chrome Strong ({cam})",
    f"Fuji Classic Chrome + Color Chrome Strong + FX Blue Strong ({cam})",
    f"Fuji Color Chrome Effect Strong ({cam})",
]
luts = {n: L.read_cube(f"{lut_dir}/{n}.cube") for n in names}


def chroma(rgb):
    lab = L.srgb_to_oklab(rgb)
    return lab[..., 0], np.hypot(lab[..., 1], lab[..., 2])


num = den = 0.0
for i, path in enumerate(raws):
    with rawpy.imread(path) as r:
        print(os.path.basename(path), f"{r.sizes.raw_width}x{r.sizes.raw_height}", end="")
        lin = r.postprocess(gamma=(1, 1), no_auto_bright=True, use_camera_wb=True,
                            output_color=rawpy.ColorSpace.sRGB, output_bps=16, half_size=True)
    lin = lin.astype(np.float64) / 65535.0
    step = max(1, lin.shape[1] // 640)
    lin = lin[::step, ::step]
    base = L.agx_display(lin)
    tiles = [("RapidRAW AgX (no LUT)", base)]
    for n in names:
        tiles.append((n.replace("Fuji ", "").replace(f" ({cam})", ""), np.clip(L.apply_lut(luts[n], base), 0, 1)))
    truth = L.apply_lut(CC_FULL, np.clip(L.linear_to_srgb(lin), 0, 1))
    tiles.append(("reference: measured CC on flat render", truth))

    l0, c0 = chroma(base)
    l1, c1 = chroma(tiles[1][1])
    lt, ct = chroma(truth)
    m = (c1 > 0.02) & (lt > 0.2) & (lt < 0.9)
    num += (ct[m] * c1[m]).sum()
    den += (c1[m] ** 2).sum()
    err = np.abs(tiles[1][1] - truth)
    print(f" | LUT vs reference: mean abs err {err.mean()*255:.2f}/255, p99 {np.percentile(err, 99)*255:.1f}", end="")
    print(f" mean chroma  agx {c0.mean():.4f}  lut {c1.mean():.4f}  reference {ct.mean():.4f}"
          f" | mean L  agx {l0.mean():.3f}  lut {l1.mean():.3f}  reference {lt.mean():.3f}")

    h, w = base.shape[:2]
    sheet = Image.new("RGB", (w * 3, (h + 22) * 2), "black")
    d = ImageDraw.Draw(sheet)
    for k, (label, im) in enumerate(tiles):
        x, y = (k % 3) * w, (k // 3) * (h + 22)
        sheet.paste(Image.fromarray((im * 255 + 0.5).astype(np.uint8)), (x, y + 22))
        d.text((x + 4, y + 5), label, fill="white")
    sheet.save(f"{out_dir}/sheet_{i}.jpg", quality=88)

print(f"chroma gain that would match the reference: {num / den:.3f}")
