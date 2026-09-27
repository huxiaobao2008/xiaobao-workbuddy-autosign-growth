#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WorkBuddy 客户端 at-rest 字段解密（$wbEncrypted 信封）· 纯标准库实现。

项目要求「零依赖（只用标准库）」，因此这里不用任何第三方加密库，
自己实现 AES-256-GCM。只需解密（GCM 解密只用到 AES 的**加密**方向），
且每次只解几百字节，纯 Python 完全够用。

算法来源：对运行版 `D:\\Program Files\\WorkBuddy\\resources\\app.asar`
逐字节核对得到（非猜测）：

    envelope = base64( JSON {suite, keyId, nonce, authTag, ciphertext} )
    明文     = AES-256-GCM(key, nonce, ciphertext, authTag, AAD)

    AAD = buildAuthenticatedContextAad(keyId, suite, {framing:"field"}, "sym-v1")
        = "WB-AAD\\0"
        | 0x01                                  # AAD 版本
        | lenpref("WBEV1")                      # STANDARD_FORMAT_ID["field"]
        | lenpref("sym-v1")                     # scheme
        | uint32(suite)                         # 大端
        | lenpref(keyId)                        # 16 位小写 hex
        | 0x02                                  # FRAMING_CODE["field"]
        | 0x00                                  # encodeOptionalUint64(undefined)
        | 0x00                                  # final === undefined

    lenpref(s) = uint32(len(s)) ++ s(utf8)      # 大端长度前缀
"""

import base64
import json
import os

# ---------------------------------------------------------------- AES-256 ---


def _build_sbox():
    """按定义生成 S-box（避免手抄 256 个字节出错）。"""
    sbox = [0] * 256
    p = q = 1
    while True:
        # p *= 3 (GF(2^8))
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
        # q /= 3 (GF(2^8))
        q ^= (q << 1) & 0xFF
        q ^= (q << 2) & 0xFF
        q ^= (q << 4) & 0xFF
        if q & 0x80:
            q ^= 0x09
        x = (
            q
            ^ ((q << 1) | (q >> 7))
            ^ ((q << 2) | (q >> 6))
            ^ ((q << 3) | (q >> 5))
            ^ ((q << 4) | (q >> 4))
        )
        sbox[p] = (x ^ 0x63) & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    return sbox


_SBOX = _build_sbox()


def _xtime(a):
    a <<= 1
    if a & 0x100:
        a = (a ^ 0x1B) & 0xFF
    return a & 0xFF


def _expand_key(key):
    nk = len(key) // 4  # AES-256 -> 8
    nr = nk + 6  # -> 14
    w = [list(key[4 * i : 4 * i + 4]) for i in range(nk)]
    rcon = 1
    for i in range(nk, 4 * (nr + 1)):
        t = list(w[i - 1])
        if i % nk == 0:
            t = t[1:] + t[:1]  # RotWord
            t = [_SBOX[b] for b in t]  # SubWord
            t[0] ^= rcon
            rcon = ((rcon << 1) ^ 0x1B) & 0xFF if rcon & 0x80 else (rcon << 1) & 0xFF
        elif nk > 6 and i % nk == 4:
            t = [_SBOX[b] for b in t]
        w.append([w[i - nk][j] ^ t[j] for j in range(4)])
    return w, nr


def _shift_rows(s):
    out = [0] * 16
    for c in range(4):
        for r in range(4):
            out[r + 4 * c] = s[r + 4 * ((c + r) % 4)]
    return out


def _mix_columns(s):
    out = [0] * 16
    for c in range(4):
        a0, a1, a2, a3 = s[4 * c : 4 * c + 4]
        out[4 * c + 0] = _xtime(a0) ^ (_xtime(a1) ^ a1) ^ a2 ^ a3
        out[4 * c + 1] = a0 ^ _xtime(a1) ^ (_xtime(a2) ^ a2) ^ a3
        out[4 * c + 2] = a0 ^ a1 ^ _xtime(a2) ^ (_xtime(a3) ^ a3)
        out[4 * c + 3] = (_xtime(a0) ^ a0) ^ a1 ^ a2 ^ _xtime(a3)
    return out


def _encrypt_block(w, nr, block):
    s = list(block)
    for i in range(16):
        s[i] ^= w[i // 4][i % 4]
    for rnd in range(1, nr):
        s = [_SBOX[b] for b in s]
        s = _shift_rows(s)
        s = _mix_columns(s)
        for i in range(16):
            s[i] ^= w[rnd * 4 + i // 4][i % 4]
    s = [_SBOX[b] for b in s]
    s = _shift_rows(s)
    for i in range(16):
        s[i] ^= w[nr * 4 + i // 4][i % 4]
    return bytes(s)


_R = 0xE1 << 120


def _gmul(x, y):
    """GF(2^128) 乘法（GCM 用的反射位序：bit0 对应最高次项）。"""
    z = 0
    v = y
    for i in range(128):
        if (x >> (127 - i)) & 1:
            z ^= v
        if v & 1:
            v = (v >> 1) ^ _R
        else:
            v >>= 1
    return z


def _ghash(h, data):
    """GHASH_H(X)：Y_0=0；Y_i = (Y_{i-1} ^ X_i) · H。逐位实现，数据量小，够用。"""
    hi = int.from_bytes(h, "big")
    res = 0
    for i in range(0, len(data), 16):
        blk = data[i : i + 16]
        if len(blk) < 16:
            blk = blk + b"\x00" * (16 - len(blk))
        res = _gmul(res ^ int.from_bytes(blk, "big"), hi)
    return res.to_bytes(16, "big")


def gcm_decrypt(key, nonce, ciphertext, auth_tag, aad):
    """AES-256-GCM 解密并校验 authTag；失败抛 ValueError。"""
    w, nr = _expand_key(key)
    h = _encrypt_block(w, nr, b"\x00" * 16)
    j0 = nonce + b"\x00\x00\x00\x01"

    # 注意：GCM 的明文密钥流从 inc32(J0) 开始；J0 本身只用于算 authTag。
    ks = b""
    base, ctr0 = j0[:12], int.from_bytes(j0[12:16], "big")
    i = 1
    while len(ks) < len(ciphertext):
        ks += _encrypt_block(w, nr, base + ((ctr0 + i) & 0xFFFFFFFF).to_bytes(4, "big"))
        i += 1
    plain = bytes(a ^ b for a, b in zip(ciphertext, ks))

    pad = lambda b: b + b"\x00" * ((-len(b)) % 16)
    s = _ghash(
        h,
        pad(aad)
        + pad(ciphertext)
        + (len(aad) * 8).to_bytes(8, "big")
        + (len(ciphertext) * 8).to_bytes(8, "big"),
    )
    tag = bytes(a ^ b for a, b in zip(s, _encrypt_block(w, nr, j0)))
    if tag[: len(auth_tag)] != auth_tag:
        raise ValueError("AtRest: authTag 校验失败（密钥不对或密文被改）")
    return plain


# ------------------------------------------------------------------- AAD ---

_LENPREF_CACHE = {}


def _lenpref(s):
    b = _LENPREF_CACHE.get(s)
    if b is None:
        raw = s.encode("utf8")
        b = len(raw).to_bytes(4, "big") + raw
        _LENPREF_CACHE[s] = b
    return b


def build_aad(key_id, suite, framing="field"):
    """复刻 buildAuthenticatedContextAad() 的 sym-v1 分支。"""
    fmt = "WBEV1" if framing == "field" else "WBEF1"
    code = 2 if framing == "field" else 1
    return (
        b"WB-AAD\x00"
        + bytes([1])
        + _lenpref(fmt)
        + _lenpref("sym-v1")
        + int(suite).to_bytes(4, "big")
        + _lenpref(key_id)
        + bytes([code])
        + bytes([0])
        + bytes([0])
    )


# ------------------------------------------------------------- 信封解密 ---


def is_envelope(v):
    return isinstance(v, dict) and v.get("$wbEncrypted") is not None


def parse_envelope(v):
    """{"$wbEncrypted":1,"envelope":"<b64>"} -> dict"""
    raw = v.get("envelope")
    if not raw:
        raise ValueError("AtRest: 信封缺少 envelope 字段")
    return json.loads(base64.b64decode(raw))


def decrypt_envelope(v, key):
    """解一个 $wbEncrypted 字段 -> 明文字符串。"""
    e = parse_envelope(v)
    aad = build_aad(e["keyId"], e.get("suite", 1), "field")
    return gcm_decrypt(
        key,
        base64.b64decode(e["nonce"]),
        base64.b64decode(e["ciphertext"]),
        base64.b64decode(e["authTag"]),
        aad,
    ).decode("utf8")


def normalize_value(v, key):
    """把可能是信封的字段转成明文字符串；不是信封则原样返回。"""
    if not is_envelope(v) or key is None:
        return v
    try:
        return decrypt_envelope(v, key)
    except Exception:
        return v


def normalize_cred(cred, key):
    """原地把凭证里所有 $wbEncrypted 字段解成明文。返回解密成功的字段数。"""
    if not cred or key is None:
        return 0
    n = 0

    def walk(node):
        nonlocal n
        if isinstance(node, dict):
            if is_envelope(node):
                return
            for k, val in list(node.items()):
                if is_envelope(val):
                    try:
                        node[k] = decrypt_envelope(val, key)
                        n += 1
                    except Exception:
                        pass
                else:
                    walk(val)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(cred)
    return n




# ------------------------------------------------------------ 密钥读取 ---


def load_key(path=None):
    """从指定文件读取 32 字节十六进制静态密钥；读不到返回 None。

    path 为 None 时依次尝试环境变量 ``WORKBUDDY_ATREST_KEY`` 指向的文件、
    ``data/atrest.key``（当前目录下）、以及登录态同目录的 ``atrest.key``。
    """
    candidates: list = []
    for p in (path, os.environ.get("WORKBUDDY_ATREST_KEY")):
        if p:
            candidates.append(p)
    here = os.path.dirname(os.path.abspath(__file__))
    candidates += [
        os.path.join(here, "..", "data", "atrest.key"),
        os.path.join(here, "data", "atrest.key"),
    ]
    for p in candidates:
        if not p:
            continue
        try:
            if os.path.isfile(p):
                raw = open(p, "r", encoding="utf-8").read().strip()
                if raw:
                    key = bytes.fromhex(raw)
                    if len(key) == 32:
                        return key
        except Exception:
            continue
    return None
