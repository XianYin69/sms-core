#!/usr/bin/env python3
"""privacy.py — 背景隐私采集：须用户授权(privacy)、每笔告知、混淆+掩码+矩阵变换，文件固定 <SMS_HOME>/privacy/。"""
import os, sys, json, time, base64

KEY, COLS = 0x5A, 8


def mask(s):
    n = len(s) // 4
    return s[:n] + "*" * max(1, len(s) - 2 * n) + s[len(s) - n:] if n else "*" * len(s)


def xor(s):
    return base64.b64encode(bytes(b ^ KEY for b in s.encode("utf-8"))).decode()


def matrix(s):
    rows = [(s[i:i + COLS] + "\x00" * COLS)[:COLS] for i in range(0, len(s), COLS)]
    return "".join("".join(r[c] for r in rows) for c in range(COLS)).replace("\x00", "")


def notice(d, doc):
    body = "\n".join(["# 隐私采集告知", "", "已采集类别（混淆+掩码+矩阵变换存储）：", ""]
                     + [f"- {r['id']} · {r['category']} · {r['ts']}" for r in doc["records"]])
    open(os.path.join(d, "NOTICE.md"), "w", encoding="utf-8").write(body + "\n")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, permissions
    sms = resolve_home.ensure(); d = os.path.join(sms, "privacy"); os.makedirs(d, exist_ok=True)
    rp = os.path.join(d, "records.json"); doc = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {"records": [], "audit": []}; cmd = sys.argv[1] if len(sys.argv) > 1 else "notice"

    def save(): json.dump(doc, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if cmd == "collect":
        if not permissions.allow(sms, "privacy"):
            sys.exit("DENIED: 用户未授权隐私采集（先 permissions.py grant privacy --write）")
        rec = {"id": f"p{len(doc['records']) + 1:03d}", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "category": sys.argv[2], "masked": mask(sys.argv[3]), "obfuscated": xor(sys.argv[3]), "matrix": matrix(xor(sys.argv[3]))}
        doc["records"].append(rec); save(); notice(d, doc)
        print(f"NOTICE: 已采集「{rec['category']}」id={rec['id']}，见 NOTICE.md（已混淆/掩码/矩阵变换）")
    elif cmd == "open":
        rid, why = sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ""
        if not (permissions.allow(sms, "privacy") and permissions.allow(sms, "write")) or not why:
            sys.exit("DENIED: 解密读取仅限必要场景，须 privacy+write 授权并写明理由")
        rec = next((r for r in doc["records"] if r["id"] == rid), None)
        doc["audit"].append({"ts": time.strftime("%H:%M:%S"), "action": "open", "id": rid, "reason": why}); save()
        print(json.dumps({"id": rid, "plaintext": bytes(b ^ KEY for b in base64.b64decode(rec["obfuscated"])).decode("utf-8") if rec else None}, ensure_ascii=False))
    else:
        notice(d, doc); print(open(os.path.join(d, "NOTICE.md"), encoding="utf-8").read().rstrip())
        print("用法: notice | collect <category> <value> | open <id> <必要理由>")
