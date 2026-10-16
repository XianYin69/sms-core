#!/usr/bin/env python3
"""Pinpoint the exact bottleneck in the first prompt_pack.pack call."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chain_store as cs, chain_dfs, chains_git, prompt_pack

SMS = resolve_home.ensure()
t0 = time.perf_counter()

# 1. chains_git.ensure
t = time.perf_counter()
ok = chains_git.ensure(os.path.join(SMS, "chains"))
print("[%.1fms] chains_git.ensure ok=%s" % ((time.perf_counter() - t) * 1000, ok), flush=True)

# 2. Store creation (includes chains_git.ensure)
t = time.perf_counter()
store = cs.Store(SMS)
print("[%.1fms] Store() created" % ((time.perf_counter() - t) * 1000), flush=True)

# 3. all_frags (first call - cold)
t = time.perf_counter()
frags = store.all_frags()
print("[%.1fms] all_frags() n=%d" % ((time.perf_counter() - t) * 1000, len(frags)), flush=True)

# 4. all_frags (second call - warm)
t = time.perf_counter()
frags2 = store.all_frags()
print("[%.1fms] all_frags() warm n=%d" % ((time.perf_counter() - t) * 1000, len(frags2)), flush=True)

# 5. chain_dfs.index (first call - cold)
t = time.perf_counter()
ix = chain_dfs.index(SMS)
print("[%.1fms] chain_dfs.index() cold byid=%d" % ((time.perf_counter() - t) * 1000, len(ix["byid"])), flush=True)

# 6. chain_dfs.index (second call - warm)
t = time.perf_counter()
ix2 = chain_dfs.index(SMS)
print("[%.1fms] chain_dfs.index() warm byid=%d" % ((time.perf_counter() - t) * 1000, len(ix2["byid"])), flush=True)

# 7. seeds_for (uses cached index)
t = time.perf_counter()
sd = chain_dfs.seeds_for("只回答一个字：通", sess=chains.cur_sess(), sms=SMS)
print("[%.1fms] seeds_for n=%d" % ((time.perf_counter() - t) * 1000, len(sd)), flush=True)

# 8. Full pack (first call - cold)
t = time.perf_counter()
p = prompt_pack.pack("只回答一个字：通", 1200, sess=chains.cur_sess())
print("[%.1fms] pack() cold len=%d" % ((time.perf_counter() - t) * 1000, len(p)), flush=True)

# 9. Full pack (second call - warm)
t = time.perf_counter()
p2 = prompt_pack.pack("只回答一个字：通", 1200, sess=chains.cur_sess())
print("[%.1fms] pack() warm len=%d" % ((time.perf_counter() - t) * 1000, len(p2)), flush=True)

print("\n=== TOTAL: %.1fms ===" % ((time.perf_counter() - t0) * 1000), flush=True)