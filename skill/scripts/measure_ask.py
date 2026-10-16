#!/usr/bin/env python3
"""Full-link timing probe for agent_stream.ask — measures each stage with wall-clock deltas."""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home, chains, prompt_builder, prompt_pack, chain_dfs, chain_store as cs, skill_route, dsm, gateway, gateway_sse

SMS = resolve_home.ensure()
T = {"t0": time.perf_counter()}
def mk(name):
    def f(*a, **k):
        dt = (time.perf_counter() - T["t0"]) * 1000
        print("[%.1fms] %s" % (dt, name), flush=True)
    return f

st = mk("start")
st("resolve_home.ensure()")

# Stage 1: prompt_builder.init
t = time.perf_counter()
i0 = prompt_builder.init(SMS)
print("[%.1fms] prompt_builder.init len=%d" % ((time.perf_counter() - t) * 1000, len(i0)), flush=True)

# Stage 2: prompt_builder.build
t = time.perf_counter()
b = prompt_builder.build("只回答一个字：通", SMS)
print("[%.1fms] prompt_builder.build len=%d" % ((time.perf_counter() - t) * 1000, len(b)), flush=True)

# Stage 3: chains.conversation (includes prompt_pack.pack + chain_dfs.expand + Store().all_frags)
t = time.perf_counter()
conv = chains.conversation(compose_text := prompt_builder.init(SMS) + "\n\n" + prompt_builder.build("只回答一个字：通", SMS) + "\n\n" + skill_route.route("只回答一个字：通", SMS)[1])
print("[%.1fms] chains.conversation len=%d" % ((time.perf_counter() - t) * 1000, len(conv)), flush=True)

# Stage 4: dsm.build_env
t = time.perf_counter()
msgs = [{"role": "system", "content": gateway._sys()}, {"role": "user", "content": conv}]
env = dsm.build_env(msgs, tools=[], model="auto", dsm_cfg=dsm.cfg())
print("[%.1fms] dsm.build_env envelope=%dB sch=%s" % ((time.perf_counter() - t) * 1000, len(json.dumps(env, ensure_ascii=False)), env["sch"]), flush=True)

# Stage 5: dsm POST (non-stream, just measure HTTP round-trip)
t = time.perf_counter()
data, err, code, ct = gateway._dsm_post(dsm.ENDPOINT, env, dsm.CTYPE)
print("[%.1fms] _dsm_post code=%s ct=%s datalen=%s err=%s" % ((time.perf_counter() - t) * 1000, code, ct, len(str(data)) if data else 0, str(err)[:80]), flush=True)

# Stage 6: gateway_sse.stream (full streaming path)
t = time.perf_counter()
out_lines = []
m, note = gateway_sse.stream(msgs, lambda s: out_lines.append(s))
print("[%.1fms] gateway_sse.stream ok=%s note=%s lines=%d chars=%d" % (
    (time.perf_counter() - t) * 1000, bool(m), str(note)[:80], len(out_lines),
    sum(len(s) for s in out_lines)), flush=True)

# Stage 7: chain_dfs.index (full rebuild)
t = time.perf_counter()
ix = chain_dfs.index(SMS, force=True)
print("[%.1fms] chain_dfs.index force byid=%d grid_cells=%d" % ((time.perf_counter() - t) * 1000, len(ix["byid"]), len(ix["grid"])), flush=True)

# Stage 8: Store().all_frags
t = time.perf_counter()
frags = cs.Store(SMS).all_frags()
print("[%.1fms] Store().all_frags n=%d" % ((time.perf_counter() - t) * 1000, len(frags)), flush=True)

# Stage 9: skill_route.route
t = time.perf_counter()
sid, inj = skill_route.route("只回答一个字：通", SMS)
print("[%.1fms] skill_route.route hit=%s inj=%dB" % ((time.perf_counter() - t) * 1000, sid, len(inj)), flush=True)

print("\n=== TOTAL: %.1fms ===" % ((time.perf_counter() - T["t0"]) * 1000), flush=True)