#!/usr/bin/env python3
"""Measure individual components of chains.conversation to find the bottleneck."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chains, prompt_builder, prompt_pack, chain_dfs, chain_store as cs, skill_route, sessions_view

SMS = resolve_home.ensure()
t0 = time.perf_counter()

# sessions_view.hint
t = time.perf_counter()
h = sessions_view.hint(chains.cur_sess())
print("[%.1fms] sessions_view.hint len=%d" % ((time.perf_counter() - t) * 1000, len(h)), flush=True)

# prompt_pack.pack (includes chain_dfs.expand -> chain_dfs.index -> Store().all_frags)
t = time.perf_counter()
p = prompt_pack.pack("只回答一个字：通", 1200, sess=chains.cur_sess())
print("[%.1fms] prompt_pack.pack len=%d" % ((time.perf_counter() - t) * 1000, len(p)), flush=True)

# Second pack (warm: chain_dfs.index + _hits_cache both cached)
t = time.perf_counter()
p2 = prompt_pack.pack("只回答一个字：通", 1200, sess=chains.cur_sess())
print("[%.1fms] prompt_pack.pack (warm) len=%d" % ((time.perf_counter() - t) * 1000, len(p2)), flush=True)

# chain_dfs.expand directly
t = time.perf_counter()
e = chain_dfs.expand("只回答一个字：通", 1200, 3, SMS, chains.cur_sess())
print("[%.1fms] chain_dfs.expand len=%d" % ((time.perf_counter() - t) * 1000, len(e)), flush=True)

# chain_dfs.index (cached, should be fast second call)
t = time.perf_counter()
ix = chain_dfs.index(SMS)
print("[%.1fms] chain_dfs.index (cached) byid=%d" % ((time.perf_counter() - t) * 1000, len(ix["byid"])), flush=True)

# chain_dfs.seeds_for
t = time.perf_counter()
sd = chain_dfs.seeds_for("只回答一个字：通", sess=chains.cur_sess(), sms=SMS)
print("[%.1fms] chain_dfs.seeds_for n=%d" % ((time.perf_counter() - t) * 1000, len(sd)), flush=True)

# chain_dfs.dfs
t = time.perf_counter()
res = chain_dfs.dfs(cs.Store(SMS), sd, 3, 1200, SMS)
print("[%.1fms] chain_dfs.dfs n=%d" % ((time.perf_counter() - t) * 1000, len(res)), flush=True)

# sessions_view.conflicts
t = time.perf_counter()
c = sessions_view.conflicts(chains.cur_sess())
print("[%.1fms] sessions_view.conflicts len=%d" % ((time.perf_counter() - t) * 1000, len(c)), flush=True)

# sessions_view._pend (reads all task tables)
t = time.perf_counter()
pd = sessions_view._pend()
print("[%.1fms] sessions_view._pend n=%d" % ((time.perf_counter() - t) * 1000, len(pd)), flush=True)

print("\n=== TOTAL: %.1fms ===" % ((time.perf_counter() - t0) * 1000), flush=True)