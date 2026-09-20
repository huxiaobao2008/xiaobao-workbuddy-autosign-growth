#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 app.asar 里搜「专家团」相关的事件/接口名。"""
import sys

P = r"D:\Program Files\WorkBuddy\resources\app.asar"
PATS = ["expert_team", "expertTeam", "ExpertTeam", "team_summon", "summonTeam",
        "summon_team", "team_summon_complete", "专家团", "expert_5",
        "Expert_team", "growth", "report_event", "track_event", "trackEvent"]


def main():
    with open(P, "rb") as f:
        data = f.read()
    print("asar size", len(data))
    for s in PATS:
        b = s.encode("utf-8")
        idxs, st = [], 0
        while len(idxs) < 8:
            i = data.find(b, st)
            if i < 0:
                break
            idxs.append(i)
            st = i + 1
        print("=== %s : %d hits" % (s, len(idxs)))
        for i in idxs:
            seg = data[max(0, i - 130):i + 200].decode("utf-8", "replace").replace("\n", " ")
            print("    ", seg[:320])
    return 0


if __name__ == "__main__":
    sys.exit(main())
