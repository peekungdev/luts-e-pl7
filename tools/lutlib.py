"""Shared colour maths for the E-PL3 / RapidRAW Classic Chrome LUT build."""
import numpy as np
from PIL import Image


# ---------- sRGB transfer ----------
def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((np.maximum(c, 0) + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.maximum(np.asarray(c, dtype=np.float64), 0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


# ---------- OKLab (Bjorn Ottosson) ----------
_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])
_M1i = np.linalg.inv(_M1)
_M2i = np.linalg.inv(_M2)


def srgb_to_oklab(rgb):
    lms = srgb_to_linear(rgb) @ _M1.T
    return np.cbrt(lms) @ _M2.T


def oklab_to_srgb(lab):
    lms = (lab @ _M2i.T) ** 3
    return linear_to_srgb(lms @ _M1i.T)


# ---------- 3D LUT helpers.  LUT arrays are indexed [r, g, b, channel]. ----------
def load_hald(path):
    im = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64) / 255.0
    n = round((im.shape[0] * im.shape[1]) ** (1 / 3))
    assert n ** 3 == im.shape[0] * im.shape[1], "not a HaldCLUT"
    # Hald order: red fastest, then green, then blue
    return im.reshape(n, n, n, 3).transpose(2, 1, 0, 3)  # -> [r, g, b]


def identity(n):
    a = np.linspace(0, 1, n)
    r, g, b = np.meshgrid(a, a, a, indexing="ij")
    return np.stack([r, g, b], -1)


def apply_lut(lut, rgb):
    """Trilinear lookup of rgb (..., 3) in lut [r, g, b, 3]."""
    n = lut.shape[0]
    shp = rgb.shape
    p = np.clip(rgb.reshape(-1, 3), 0, 1) * (n - 1)
    i0 = np.minimum(np.floor(p).astype(np.int64), n - 2)
    f = p - i0
    out = np.zeros_like(p)
    for dr in (0, 1):
        wr = f[:, 0] if dr else 1 - f[:, 0]
        for dg in (0, 1):
            wg = f[:, 1] if dg else 1 - f[:, 1]
            for db in (0, 1):
                wb = f[:, 2] if db else 1 - f[:, 2]
                out += (wr * wg * wb)[:, None] * lut[i0[:, 0] + dr, i0[:, 1] + dg, i0[:, 2] + db]
    return out.reshape(shp)


def smooth(lut, passes=1):
    """Light separable [1 2 1]/4 blur of the *offset from identity*, edges replicated."""
    d = lut - identity(lut.shape[0])
    for _ in range(passes):
        for ax in range(3):
            pad = [(0, 0)] * 4
            pad[ax] = (1, 1)
            e = np.pad(d, pad, mode="edge")
            sl = [slice(None)] * 4
            a, b, c = list(sl), list(sl), list(sl)
            a[ax], b[ax], c[ax] = slice(0, -2), slice(1, -1), slice(2, None)
            d = 0.25 * e[tuple(a)] + 0.5 * e[tuple(b)] + 0.25 * e[tuple(c)]
    return identity(lut.shape[0]) + d


def write_cube(path, lut, title, comments=()):
    n = lut.shape[0]
    data = np.clip(lut, 0, 1).transpose(2, 1, 0, 3).reshape(-1, 3)  # red fastest
    with open(path, "w", encoding="ascii", newline="\n") as f:
        for c in comments:
            f.write(f"# {c}\n")
        f.write(f'TITLE "{title}"\n')
        f.write(f"LUT_3D_SIZE {n}\n")
        f.write("DOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n")
        for r, g, b in data:
            f.write(f"{r:.6f} {g:.6f} {b:.6f}\n")


def read_cube(path):
    n, rows = None, []
    with open(path, encoding="ascii") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            k = s.split()
            if k[0] == "LUT_3D_SIZE":
                n = int(k[1])
            elif k[0] in ("TITLE", "DOMAIN_MIN", "DOMAIN_MAX"):
                continue
            else:
                rows.append([float(v) for v in k[:3]])
    a = np.array(rows)
    assert n and a.shape == (n ** 3, 3)
    return a.reshape(n, n, n, 3).transpose(2, 1, 0, 3)


# ---------- RapidRAW's AgX display transform (port of shader.wgsl / image_processing.rs) ----------
def _prim_to_xyz(prim, wp):
    def xyz(xy):
        return np.array([xy[0] / xy[1], 1.0, (1 - xy[0] - xy[1]) / xy[1]])
    m = np.stack([xyz(p) for p in prim], 1)
    s = np.linalg.solve(m, xyz(wp))
    return m * s


def _rot_scale(p, wp, scale, rot):
    d = (np.array(p) - wp) * scale
    s, c = np.sin(rot), np.cos(rot)
    return wp + np.array([d[0] * c - d[1] * s, d[0] * s + d[1] * c])


def agx_matrices():
    wp = np.array([0.3127, 0.3290])
    srgb = [(0.64, 0.33), (0.30, 0.60), (0.15, 0.06)]
    r2020 = [(0.708, 0.292), (0.170, 0.797), (0.131, 0.046)]
    inset = [0.2946245, 0.25861925, 0.14641371]
    rot = [0.03540329, -0.02108586, -0.06305724]
    outset = [0.2907764, 0.2631554, 0.04581072]
    base_to_xyz = _prim_to_xyz(r2020, wp)
    xyz_to_base = np.linalg.inv(base_to_xyz)
    pipe_to_base = xyz_to_base @ _prim_to_xyz(srgb, wp)
    rend = [_rot_scale(r2020[i], wp, 1 - inset[i], rot[i]) for i in range(3)]
    base_to_rendering = xyz_to_base @ _prim_to_xyz(rend, wp)
    outp = [_rot_scale(r2020[i], wp, 1 - outset[i], 0.0) for i in range(3)]
    rendering_to_base = np.linalg.inv(xyz_to_base @ _prim_to_xyz(outp, wp))
    return base_to_rendering @ pipe_to_base, np.linalg.inv(pipe_to_base) @ rendering_to_base


def _agx_curve(x):
    slope, tx, ty = 2.3843, 0.6060606, 0.43446

    def sig(v, p=1.5):
        return v / (1 + np.abs(v) ** p) ** (1 / p)

    toe = -1.0359 * sig(slope * (x - tx) / -1.0359) + ty
    sho = 1.3475 * sig(slope * (x - tx) / 1.3475) + ty
    return np.clip(np.where(x < tx, toe, sho), 0, 1)


def agx_display(lin):
    """Scene-linear sRGB-primaries RGB -> RapidRAW AgX display RGB."""
    a, b = agx_matrices()
    c = np.asarray(lin, dtype=np.float64)
    mn = c.min(-1, keepdims=True)
    c = np.where(mn < 0, c - mn, c)
    c = c @ a.T
    x = np.clip((np.log2(np.maximum(c / 0.18, 1e-6)) + 15.2) / 20.2, 0, 1)
    return np.clip((_agx_curve(x) ** 2.4) @ b.T, 0, 1)


def basic_display(lin):
    """RapidRAW's non-AgX raw display transform."""
    s = linear_to_srgb(np.clip(lin, 0, None)) ** (1 / 1.1)
    s = np.clip(s, 0, 1)
    return 0.25 * s + 0.75 * (s * s * (3 - 2 * s))
