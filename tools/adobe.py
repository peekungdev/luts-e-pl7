"""Adobe Camera Raw / Lightroom pieces, ported from Adobe's DNG SDK (1.7.1).

* acr3_curve(): the default ACR3 tone curve.  It is read at run time from the
  SDK's dng_render.cpp so no Adobe code is copied into this repository.
* adobe_display(): an "Adobe Standard"-like rendering: scene-linear sRGB ->
  ProPhoto -> RefBaselineRGBTone(ACR3 curve) -> sRGB-encoded display RGB.
  This is the image a profile's RGB table receives in dng_render.cpp, where
  RGB tables run right after the tone curve.
* encode_rgb_table() / decode_rgb_table(): the crs:Table_<md5> string format
  (dng_big_table::EncodeAsString / DecodeFromString, dng_rgb_table::PutStream).
* write_profile(): a Camera Raw "creative profile" .xmp (PresetType="Look").
"""
import hashlib
import re
import struct
import uuid
import zlib
import numpy as np

import lutlib as L

# ---------------------------------------------------------------- tone curve
_curve = None


def load_acr3_curve(dng_render_cpp):
    """Parse dng_tone_curve_acr3_default::Evaluate's kTable from the SDK source."""
    global _curve
    src = open(dng_render_cpp, encoding="utf-8", errors="replace").read()
    body = src[src.index("dng_tone_curve_acr3_default::Evaluate"):]
    body = body[body.index("kTable"):body.index("};")]
    vals = np.array([float(v) for v in re.findall(r"([0-9]*\.[0-9]+)f", body)])
    assert len(vals) == 1025 and vals[0] == 0 and vals[-1] == 1, len(vals)
    _curve = vals
    return vals


def acr3(x):
    x = np.clip(x, 0, 1) * (len(_curve) - 1)
    i = np.minimum(x.astype(np.int64), len(_curve) - 2)
    f = x - i
    return _curve[i] * (1 - f) + _curve[i + 1] * f


# ------------------------------------------------------------ colour spaces
_PROPHOTO = [(0.734699, 0.265301), (0.159597, 0.840403), (0.036598, 0.000105)]
_D50 = np.array([0.3457, 0.3585])
_D65 = np.array([0.3127, 0.3290])


def _bradford(src_wp, dst_wp):
    m = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]])
    def xyz(xy):
        return np.array([xy[0] / xy[1], 1, (1 - xy[0] - xy[1]) / xy[1]])
    s, d = m @ xyz(src_wp), m @ xyz(dst_wp)
    return np.linalg.inv(m) @ np.diag(d / s) @ m


SRGB_TO_PROPHOTO = (np.linalg.inv(L._prim_to_xyz(_PROPHOTO, _D50))
                    @ _bradford(_D65, _D50) @ L._prim_to_xyz([(0.64, 0.33), (0.30, 0.60), (0.15, 0.06)], _D65))
PROPHOTO_TO_SRGB = np.linalg.inv(SRGB_TO_PROPHOTO)


def rgb_tone(c):
    """RefBaselineRGBTone: curve on max and min channel, middle keeps its ratio."""
    c = np.clip(c, 0, 1)
    hi, lo = c.max(-1, keepdims=True), c.min(-1, keepdims=True)
    thi, tlo = acr3(hi), acr3(lo)
    with np.errstate(invalid="ignore", divide="ignore"):
        t = np.where(hi > lo, (c - lo) / (hi - lo), 0.0)
    out = tlo + (thi - tlo) * t
    return np.where(hi > lo, out, acr3(c))


def adobe_display(lin_srgb):
    """Scene-linear sRGB -> Adobe-Standard-like display sRGB (encoded)."""
    pp = np.clip(lin_srgb @ SRGB_TO_PROPHOTO.T, 0, None)
    return np.clip(L.linear_to_srgb(rgb_tone(pp) @ PROPHOTO_TO_SRGB.T), 0, 1)


def adobe_inverse(x, iters=40):
    """Display sRGB -> scene-linear sRGB, by inverting adobe_display numerically."""
    target = np.clip(L.srgb_to_linear(x), 0, 1) @ SRGB_TO_PROPHOTO.T   # toned ProPhoto
    lut_x = np.linspace(0, 1, 65537)
    inv1 = lambda v: np.interp(np.clip(v, 0, 1), acr3(lut_x), lut_x)   # 1-D curve inverse
    pp = inv1(target)                                                  # good first guess
    for _ in range(iters):
        pp = np.clip(pp + 0.8 * (inv1(target) - inv1(rgb_tone(pp))), 0, 1)
    return np.maximum(pp @ PROPHOTO_TO_SRGB.T, 0)


# ------------------------------------------------- crs:Table_ string format
_ENC = ("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ".-:+=^!/*?`'|()[]{}@%$#")
assert len(_ENC) == 85
_DEC = {c: i for i, c in enumerate(_ENC)}

BTT_RGBTABLE, RGBTABLE_VERSION = 1, 1
PRIMARIES_SRGB, GAMMA_SRGB, GAMUT_CLIP = 0, 1, 0


def _nop(n):
    return [(i * 0xFFFF + (n >> 1)) // (n - 1) for i in range(n)]


def rgb_table_stream(lut, min_amount=0.0, max_amount=2.0):
    """dng_rgb_table::PutStream for a 3-D table; lut is [r, g, b, 3] in 0..1."""
    n = lut.shape[0]
    assert lut.shape == (n, n, n, 3) and 2 <= n <= 32
    nop = np.array(_nop(n), dtype=np.int64)
    s = np.round(np.clip(lut, 0, 1) * 65535).astype(np.int64)        # r outer, b inner
    d = np.empty_like(s)
    d[..., 0] = s[..., 0] - nop[:, None, None]
    d[..., 1] = s[..., 1] - nop[None, :, None]
    d[..., 2] = s[..., 2] - nop[None, None, :]
    out = struct.pack("<4I", BTT_RGBTABLE, RGBTABLE_VERSION, 3, n)
    out += (d & 0xFFFF).astype("<u2").tobytes()
    out += struct.pack("<3I2d", PRIMARIES_SRGB, GAMMA_SRGB, GAMUT_CLIP, min_amount, max_amount)
    return out


def encode_rgb_table(lut):
    """Return (fingerprint hex, encoded string) exactly as Camera Raw stores them."""
    raw = rgb_table_stream(lut)
    fp = hashlib.md5(raw).hexdigest().upper()
    comp = struct.pack("<I", len(raw)) + zlib.compress(raw, 6)
    n = len(comp)
    buf = comp + b"\0\0\0"
    out, i = [], 0
    while n:
        x = int.from_bytes(buf[i:i + 4], "little")
        i += 4
        digits = []
        for _ in range(5):
            digits.append(x % 85)
            x //= 85
        take = 5 if n >= 4 else n + 1
        out.extend(_ENC[dgt] for dgt in digits[:take])
        n -= min(n, 4)
    return fp, "".join(out)


def decode_rgb_table(s):
    """Inverse of encode_rgb_table (mirrors dng_big_table::DecodeFromString)."""
    vals = [_DEC[c] for c in s]
    data = bytearray()
    for k in range(0, len(vals), 5):
        g = vals[k:k + 5]
        x = sum(v * 85 ** j for j, v in enumerate(g))
        data += x.to_bytes(4, "little")[:len(g) - 1]
    size = struct.unpack("<I", data[:4])[0]
    raw = zlib.decompress(bytes(data[4:]))
    assert len(raw) == size
    btt, ver, dims, n = struct.unpack("<4I", raw[:16])
    assert (btt, ver, dims) == (BTT_RGBTABLE, RGBTABLE_VERSION, 3)
    d = np.frombuffer(raw[16:16 + n ** 3 * 6], "<u2").astype(np.int64).reshape(n, n, n, 3)
    nop = np.array(_nop(n))
    s3 = d.copy()
    s3[..., 0] += nop[:, None, None]
    s3[..., 1] += nop[None, :, None]
    s3[..., 2] += nop[None, None, :]
    tail = struct.unpack("<3I2d", raw[16 + n ** 3 * 6:16 + n ** 3 * 6 + 28])
    return (s3 & 0xFFFF) / 65535.0, tail, hashlib.md5(raw).hexdigest().upper()


# ------------------------------------------------------------ profile .xmp
def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def write_profile(path, lut, name, group, copyright_=""):
    fp, enc = encode_rgb_table(lut)
    pid = uuid.uuid5(uuid.NAMESPACE_URL, "luts-e-pl7/" + name).hex.upper()
    alt = lambda v: (f'    <rdf:Alt>\n     <rdf:li xml:lang="x-default">{_esc(v)}</rdf:li>\n    </rdf:Alt>\n')
    xmp = (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 7.0-c000 1.000000, 0000/00/00-00:00:00        ">\n'
        ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '  <rdf:Description rdf:about=""\n'
        '    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"\n'
        '   crs:PresetType="Look"\n'
        '   crs:Cluster=""\n'
        f'   crs:UUID="{pid}"\n'
        '   crs:SupportsAmount="True"\n'
        '   crs:SupportsColor="True"\n'
        '   crs:SupportsMonochrome="False"\n'
        '   crs:SupportsHighDynamicRange="True"\n'
        '   crs:SupportsNormalDynamicRange="True"\n'
        '   crs:SupportsSceneReferred="True"\n'
        '   crs:SupportsOutputReferred="True"\n'
        '   crs:RequiresRGBTables="False"\n'
        '   crs:CameraModelRestriction=""\n'
        f'   crs:Copyright="{_esc(copyright_)}"\n'
        '   crs:ContactInfo=""\n'
        '   crs:Version="14.3"\n'
        '   crs:ProcessVersion="11.0"\n'
        '   crs:ConvertToGrayscale="False"\n'
        f'   crs:RGBTable="{fp}"\n'
        f'   crs:Table_{fp}="{enc}"\n'
        '   crs:HasSettings="True">\n'
        f'   <crs:Name>\n{alt(name)}   </crs:Name>\n'
        f'   <crs:ShortName>\n{alt(name)}   </crs:ShortName>\n'
        f'   <crs:SortName>\n{alt(name)}   </crs:SortName>\n'
        f'   <crs:Group>\n{alt(group)}   </crs:Group>\n'
        f'   <crs:Description>\n{alt("Fujifilm Classic Chrome style look, calibrated for Adobe rendering. github.com/peekungdev/luts-e-pl7")}   </crs:Description>\n'
        '  </rdf:Description>\n'
        ' </rdf:RDF>\n'
        '</x:xmpmeta>\n')
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(xmp)
    return fp
