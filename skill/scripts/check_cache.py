#!/usr/bin/env python3
"""Check .fcz cache state."""
import os, sys, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home
SMS = resolve_home.ensure()
cache_dir = os.path.join(SMS, "chains", ".cache")
print("SMS:", SMS)
print("cache_dir:", cache_dir)
for f in sorted(os.listdir(cache_dir)):
    if not f.endswith(".fcz"):
        continue
    p = os.path.join(cache_dir, f)
    try:
        with open(p, "rb") as fh:
            doc = pickle.load(fh)
        chain = f[:-4]
        ver = doc.get("ver")
        entries = doc.get("entries", {})
        print("%s: ver=%s chain=%s entries=%d" % (f, ver, doc.get("chain"), len(entries)))
        if ver != 3:
            print("  *** STALE VERSION ***")
    except Exception as e:
        print("%s: ERROR %s" % (f, e))