"""Build the Capture One version: a style (.costyle) that approximates Classic Chrome.

Capture One cannot load 3-D LUTs, so the look is re-expressed with adjustments
it has on every camera: Saturation, then the Red / Green / Blue curves.  These
are fitted to the Lightroom table, because both programs apply styles/profiles
on top of a contrasty default rendering (Capture One's film curve, Adobe's
tone curve).  Hue-specific effects (Color Chrome Effect / FX Blue) cannot be
expressed this way and are not offered for Capture One.

Usage: build_captureone.py <ref_dir> <dng_render.cpp from the DNG SDK> <out_dir> [camera label]
"""
import os
import sys
import uuid
import numpy as np

import lutlib as L
import adobe as A
from build import shoulder, agx_inverse

KNOTS = np.linspace(0, 1, 9)
LUMA = np.array([0.2126, 0.7152, 0.0722])


def saturate(x, s):
    y = (x @ LUMA)[..., None]
    return np.clip(y + s * (x - y), 0, 1)


def fit(look, x, w):
    """Curves taken exactly from the grey axis, then the saturation factor that
    best matches the look on the sample colours (greys are unaffected by it)."""
    v = np.repeat(KNOTS[:, None], 3, 1)
    grey = look(v)                                     # (knots, 3): R, G, B response to grey
    knots = [np.maximum.accumulate(np.clip(grey[:, c], 0, 1)) for c in range(3)]
    target = look(x)
    best = min((np.average(np.abs(apply_style(x, s, knots) - target).mean(-1), weights=w), s)
               for s in np.arange(0.50, 1.201, 0.01))
    return best[1], knots, target


def apply_style(x, s, knots):
    xs = saturate(x, s)
    return np.stack([np.interp(xs[..., c], KNOTS, knots[c]) for c in range(3)], -1)


def write_costyle(path, name, s, knots):
    sat = int(round((s - 1) * 100))
    curve = lambda k: ";".join(f"{a:.6g},{b:.6g}" for a, b in zip(KNOTS, k))
    lines = [
        '<?xml version="1.0"?>',
        '<SL Engine="900">',
        f'\t<E K="GradationCurveBlue" V="{curve(knots[2])}" />',
        f'\t<E K="GradationCurveGreen" V="{curve(knots[1])}" />',
        f'\t<E K="GradationCurveRed" V="{curve(knots[0])}" />',
        f'\t<E K="Name" V="{name}" />',
        f'\t<E K="Saturation" V="{sat}" />',
        '\t<E K="StyleSource" V="Styles" />',
        f'\t<E K="UUID" V="{str(uuid.uuid5(uuid.NAMESPACE_URL, "luts-e-pl7/" + name)).upper()}" />',
        '</SL>',
    ]
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
    return sat


def main():
    ref, dng_render, out = sys.argv[1:4]
    cam = sys.argv[4] if len(sys.argv) > 4 else "E-PL7"
    A.load_acr3_curve(dng_render)
    CC = L.load_hald(os.path.join(ref, "Classic_Chrome.png"))
    grey = np.full((1, 3), 0.5)
    k = float(agx_inverse(grey)[0, 1] / A.adobe_inverse(grey)[0, 1])

    def look(x):
        return L.apply_lut(CC, np.clip(L.linear_to_srgb(shoulder(k * A.adobe_inverse(x))), 0, 1))

    # Sample colours: a display-space grid, weighted strongly towards the low-
    # and mid-chroma colours that make up most of a real photo.
    x = L.identity(25).reshape(-1, 3)
    lab = L.srgb_to_oklab(x)
    w = np.exp(-(np.hypot(lab[:, 1], lab[:, 2]) / 0.08) ** 2)

    s, knots, target = fit(look, x, w)
    os.makedirs(out, exist_ok=True)
    name = f"Fuji Classic Chrome ({cam})"
    sat = write_costyle(os.path.join(out, name + ".costyle"), name, s, knots)
    err = np.average(np.abs(apply_style(x, s, knots) - target).mean(-1), weights=w) * 255
    print(f"saturation factor {s:.2f} -> slider {sat:+d}; weighted grid error {err:.2f}/255")
    for c, ch in enumerate("RGB"):
        print(ch, np.round(knots[c], 3).tolist())


if __name__ == "__main__":
    main()
