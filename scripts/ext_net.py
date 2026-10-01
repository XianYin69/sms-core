#!/usr/bin/env python3
"""ext_net.py — 后量子非对称核（对外端口验签）：后端自动探测——cryptography.mldsa（ML-DSA-65，FIPS 204 后量子签名）首选，退回 ed25519（classic）；公钥 DER·base64，指纹＝sha256(公钥DER)；信任表 <SMS_HOME>/shell/external/trusted.json（须本地端 `external.py enroll` 批准，存 pub/note/到期）；挑战 nonce 60 秒一次性匹配。用法：python -B ext_net.py backend|keygen|fpr <pub_b64>|list|revoke <fpr>。"""
import os, sys, json, time, base64, hashlib, threading
from cryptography.hazmat.primitives.serialization import load_der_public_key, Encoding, PublicFormat
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home
_B = None
def ts(t=None): return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))
def backend():
    global _B
    if not _B:
        try: from cryptography.hazmat.primitives.asymmetric import mldsa; _B = "mldsa65"
        except Exception: _B = "ed25519"
    return _B
def is_pq(): return backend() == "mldsa65"
def keygen():
    from cryptography.hazmat.primitives.asymmetric import mldsa, ed25519
    return mldsa.MLDSA65PrivateKey.generate() if is_pq() else ed25519.Ed25519PrivateKey.generate()
def pub_b64(sk): return base64.b64encode(sk.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)).decode()
def fpr(b64): return hashlib.sha256(base64.b64decode(b64)).hexdigest()
def sign(sk, msg): return sk.sign(msg.encode() if isinstance(msg, str) else msg)
def verify(b64, msg, sig_b64):
    try: load_der_public_key(base64.b64decode(b64)).verify(base64.b64decode(sig_b64), msg.encode() if isinstance(msg, str) else msg); return True
    except Exception: return False
def store_p(): return os.path.join(resolve_home.ensure(), "shell", "external", "trusted.json")
def load():
    try: return json.load(open(store_p(), encoding="utf-8"))
    except Exception: return []
def _wj(rows): os.makedirs(os.path.dirname(store_p()), exist_ok=True); json.dump(rows, open(store_p(), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
def enroll(b64, note="", ttl_min=0):
    rows = [r for r in load() if r["fpr"] != fpr(b64)]
    rows.append({"fpr": fpr(b64), "pub": b64, "algo": backend(), "note": note, "added": ts(), "expires": ts(time.time() + ttl_min * 60) if ttl_min else None}); _wj(rows); return fpr(b64)
def trusted(f):
    r = next((x for x in load() if x["fpr"] == f), None); return r if r and not (r.get("expires") and r["expires"] < ts()) else None
def revoke(f):
    rows = load(); keep = [x for x in rows if x["fpr"] != f]; _wj(keep); return len(rows) - len(keep)
_L = threading.Lock(); _P = {}
def challenge(f, ttl=60):
    with _L: n = os.urandom(16).hex(); _P[f] = (n, time.time() + ttl); return n
def answer(f, nonce, sig_b64):
    with _L: c = _P.pop(f, None)
    return bool(c and c[0] == nonce and time.time() <= c[1] and trusted(f) and verify(trusted(f)["pub"], nonce, sig_b64))
if __name__ == "__main__":
    a = sys.argv[1:] or ["backend"]; cmd = a[0]
    if cmd == "backend": print(json.dumps({"backend": backend(), "pq": is_pq()}, ensure_ascii=False))
    elif cmd == "keygen": b = pub_b64(keygen()); print(json.dumps({"algo": backend(), "pub_b64": b, "fpr": fpr(b), "note": "私钥留客户端；SMS 只存公钥指纹"}, ensure_ascii=False))
    elif cmd == "fpr" and a[1:]: print(fpr(a[1]))
    elif cmd == "list": print(json.dumps(load(), ensure_ascii=False, indent=1))
    elif cmd == "revoke" and a[1:]: print("吊销 " + str(revoke(a[1])) + " 条")
    else: print(__doc__.strip().splitlines()[-1])
