"""Build Fujifilm Classic Chrome / Color Chrome Effect LUTs for RapidRAW (Olympus PEN raws).

RapidRAW applies user LUTs to the *display-referred* sRGB image, after its tone
mapper and curves.  The measured Classic Chrome table (Stuart Sowerby's X-Trans
III fit) expects a flat, neutral raw conversion instead, so each LUT entry is
built by undoing RapidRAW's AgX display transform first:

    lut(x) = ClassicChrome( sRGB_encode( shoulder( AgX^-1 (x) ) ) )

i.e. the LUT swaps RapidRAW's AgX rendering for Fuji's Classic Chrome rendering
of the same scene-linear data.

Usage: build.py <ref_dir> <out_dir> [size] [camera label, e.g. E-PL7] [camera full name]
"""
import sys
import numpy as np
import lutlib as L


def agx_inverse(x):
    """RapidRAW AgX display RGB -> scene-linear RGB (sRGB primaries)."""
    a, b = L.agx_matrices()
    t = np.linspace(0, 1, 20001)
    ct = L._agx_curve(t) ** 2.4                      # monotone display value per log position
    lo, hi = np.searchsorted(ct, 1e-7), np.searchsorted(ct, 1 - 1e-7)
    v = np.clip(x @ np.linalg.inv(b).T, ct[lo], ct[hi])
    logpos = np.interp(v, ct[lo:hi + 1], t[lo:hi + 1])
    lin = 0.18 * 2.0 ** (logpos * 20.2 - 15.2)
    return np.maximum(lin @ np.linalg.inv(a).T, 0)


def shoulder(c, knee=0.7):
    """Roll scene values above the knee off towards 1.0 instead of hard-clipping,
    so pushed exposure in RapidRAW keeps a highlight gradient."""
    over = np.maximum(c - knee, 0)
    return np.where(c > knee, knee + (1 - knee) * (1 - np.exp(-over / (1 - knee))), c)


def classic_chrome(x, CC):
    return L.apply_lut(CC, np.clip(L.linear_to_srgb(shoulder(agx_inverse(x))), 0, 1))


def _smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def _hue_window(h, centre, half_width, feather):
    d = np.abs((h - centre + 180) % 360 - 180)
    return 1 - _smoothstep(half_width, half_width + feather, d)


def color_chrome(rgb, strength=0.0, blue=0.0):
    """Fujifilm Color Chrome Effect / Color Chrome FX Blue model.

    Both deepen highly saturated colours (lower lightness, chroma kept) so
    vivid subjects keep tonal gradation instead of going flat.  The main
    effect works on reds through greens; FX Blue covers the blues it skips.
    """
    lab = L.srgb_to_oklab(rgb)
    c = np.hypot(lab[..., 1], lab[..., 2])
    h = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360
    sat = _smoothstep(0.06, 0.24, c)
    warm = _hue_window(h, 85, 85, 40) + 0.45 * _hue_window(h, 340, 20, 30)   # red..green, some magenta
    cool = _hue_window(h, 255, 35, 35)                                        # cyan-blue..violet-blue
    k = np.clip(strength * np.clip(warm, 0, 1) + blue * cool, 0, 0.4) * sat
    lab[..., 0] *= 1 - k
    return np.clip(L.oklab_to_srgb(lab), 0, 1)


def main():
    ref, out = sys.argv[1], sys.argv[2]
    N = int(sys.argv[3]) if len(sys.argv) > 3 else 33
    cam = sys.argv[4] if len(sys.argv) > 4 else "E-PL3"
    cam_name = sys.argv[5] if len(sys.argv) > 5 else "Olympus PEN Lite E-PL3"
    CC = L.load_hald(f"{ref}/Classic_Chrome.png")
    look = classic_chrome(L.identity(N).reshape(-1, 3), CC).reshape(N, N, N, 3)
    g = L.apply_lut(look, np.repeat(np.linspace(0, 1, 9)[:, None], 3, 1))
    print("grey ramp ->", np.round(g, 3).tolist())

    WEAK, STRONG = 0.10, 0.20
    variants = {
        f"Fuji Classic Chrome ({cam})": (True, 0, 0),
        f"Fuji Classic Chrome + Color Chrome Weak ({cam})": (True, WEAK, 0),
        f"Fuji Classic Chrome + Color Chrome Strong ({cam})": (True, STRONG, 0),
        f"Fuji Classic Chrome + Color Chrome Strong + FX Blue Strong ({cam})": (True, STRONG, STRONG),
        f"Fuji Color Chrome Effect Strong ({cam})": (False, STRONG, 0),
        f"Fuji Color Chrome FX Blue Strong ({cam})": (False, 0, STRONG),
    }
    src = L.identity(N)
    for name, (cc, s, b) in variants.items():
        x = color_chrome(src, s, b) if (s or b) else src
        y = L.apply_lut(look, x) if cc else x
        L.write_cube(f"{out}/{name}.cube", y, name, comments=[
            name,
            "Display-referred sRGB in / sRGB out, for RapidRAW with the AgX tone mapper (its raw default).",
            f"Checked on {cam_name} raw files.",
            "Classic Chrome data: Stuart Sowerby's Fuji X-Trans III film simulation profiles (sowerby.me),",
            "re-targeted from a flat raw render to RapidRAW's AgX output.",
            "Color Chrome Effect / FX Blue: modelled, not measured.",
            "Not a Fujifilm product.",
        ])
        print("wrote", name)


if __name__ == "__main__":
    main()
