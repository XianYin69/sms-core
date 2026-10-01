#!/usr/bin/env python3
"""locality.py — 检查用户时区与地区：tz(name/offset) + locale/region，写 SMS/registry/locality.json，供会话读取。"""
import os, sys, time
from datetime import datetime


def tz():
    d = datetime.now().astimezone()
    return {"name": d.tzname(), "offset": d.strftime("%z"), "utc_seconds": int(d.utcoffset().total_seconds())}


def region():
    lang = None
    try:
        import locale
        lang = (locale.getlocale() or (None,))[0]
    except Exception:
        pass
    env = os.environ.get("LC_ALL") or os.environ.get("LANG") or ""
    return {"locale": lang or (env or None), "country": os.environ.get("SMS_COUNTRY") or None,
            "date": time.strftime("%Y-%m-%d"), "clock": time.strftime("%H:%M:%S")}


def build():
    return {"schema": "skill_locality", "version": "1.0.0",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "timezone": tz(), "region": region()}


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resolve_home, emit
    sms = resolve_home.ensure()
    print(emit.write_json(os.path.join(sms, "registry", "locality.json"), build(), sms, "--write" not in sys.argv))
