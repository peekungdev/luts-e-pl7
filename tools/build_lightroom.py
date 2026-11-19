"""Build the Lightroom / Camera Raw versions: Camera Raw creative profiles (.xmp).

A profile's RGB table is applied by Camera Raw to the *rendered* image, right
after the base profile's tone curve (see dng_render.cpp in the DNG SDK).  The
table is therefore calibrated against an Adobe-Standard-like rendering instead
of RapidRAW's AgX:

    table(x) = ClassicChrome( sRGB( shoulder( k * Adobe^-1 (x) ) ) )

Adobe's default curve renders mid-grey about 2/3 stop brighter than RapidRAW's
AgX.  k matches the two at mid-grey (display 0.5 -> the same scene value), so
the profile keeps the brightness of the photo as Lightroom showed it, like the
RapidRAW LUTs do, instead of darkening every image.

Usage: build_lightroom.py <ref_dir> <dng_render.cpp from the DNG SDK> <out_dir> [camera label]
"""
import os
import sys
import numpy as np

import lutlib as L
import adobe as A
from build import shoulder, color_chrome, agx_inverse

N = 32   # Camera Raw's long-standing limit for 3-D RGB tables


def main():
    ref, dng_render, out = sys.argv[1:4]
    cam = sys.argv[4] if len(sys.argv) > 4 else "E-PL7"
    A.load_acr3_curve(dng_render)
    CC = L.load_hald(os.path.join(ref, "Classic_Chrome.png"))
    os.makedirs(out, exist_ok=True)

    grey = np.full((1, 3), 0.5)
    k = float(agx_inverse(grey)[0, 1] / A.adobe_inverse(grey)[0, 1])
    print(f"mid-grey match: k = {k:.3f} ({np.log2(k):+.2f} EV)")

    def look(x):
        flat = np.clip(L.linear_to_srgb(shoulder(k * A.adobe_inverse(x.reshape(-1, 3)))), 0, 1)
        return L.apply_lut(CC, flat).reshape(x.shape)

    WEAK, STRONG = 0.10, 0.20
    variants = {
        "Classic Chrome": (True, 0, 0),
        "Classic Chrome + Color Chrome Weak": (True, WEAK, 0),
        "Classic Chrome + Color Chrome Strong": (True, STRONG, 0),
        "Classic Chrome + Color Chrome Strong + FX Blue Strong": (True, STRONG, STRONG),
        "Color Chrome Effect Strong": (False, STRONG, 0),
        "Color Chrome FX Blue Strong": (False, 0, STRONG),
    }
    src = L.identity(N)
    group = f"Fuji Classic Chrome ({cam})"
    for short, (cc, s, b) in variants.items():
        x = color_chrome(src, s, b) if (s or b) else src
        y = look(x) if cc else x
        name = f"Fuji {short} ({cam})"
        fp = A.write_profile(os.path.join(out, name + ".xmp"), y, name, group,
                             copyright_="GPL-3.0. Classic Chrome data: Stuart Sowerby (sowerby.me) via cedeber/hald-clut.")
        print(fp, name)


if __name__ == "__main__":
    main()
