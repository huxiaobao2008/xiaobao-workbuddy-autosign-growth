#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kill any STALE instance of this project's web server holding port 8765-8775.

Why this exists
---------------
server.py's free_port() falls back to 8766, 8767... when 8765 is taken. If an old
server is still running, the freshly opened browser keeps talking to the OLD
instance (old ui.html, old routes) -- which looks exactly like "the web page is
broken / buttons do nothing". So the launcher must get rid of the old one first.

Safety
------
Only processes that (a) LISTEN on TCP in the 8765-8775 range and (b) actually
answer GET /api/state with our server's JSON shape are terminated. A browser
holding a connection to that port is never LISTENING, so it is never touched.
"""
import json
import os
import subprocess
import sys
import urllib.request

PORT_FROM, PORT_TO = 8765, 8775


def listening_pids():
    """{port: pid} for TCP LISTENING sockets in our port range (self excluded)."""
    me = os.getpid()
    found = {}
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "tcp"],
                             capture_output=True, text=True).stdout
    except Exception as e:
        print("  [warn] netstat failed: %s" % e)
        return found
    for line in out.splitlines():
        parts = line.split()
        # TCP  <local>  <foreign>  <state>  <pid>
        if len(parts) < 5 or parts[0].upper() != "TCP" or parts[3].upper() != "LISTENING":
            continue
        try:
            port = int(parts[1].rsplit(":", 1)[1])
            pid = int(parts[4])
        except (ValueError, IndexError):
            continue
        if PORT_FROM <= port <= PORT_TO and pid != me:
            found[port] = pid
    return found


def is_our_server(port):
    """True only if the port answers /api/state with our JSON shape."""
    try:
        raw = urllib.request.urlopen(
            "http://127.0.0.1:%d/api/state" % port, timeout=1.5).read()
        data = json.loads(raw.decode("utf-8", "replace"))
        return isinstance(data, dict) and ("accounts" in data or "totals" in data)
    except Exception:
        return False


def main():
    pids = listening_pids()
    if not pids:
        print("  Nothing listening on %d-%d." % (PORT_FROM, PORT_TO))
        return 0
    killed = 0
    for port, pid in sorted(pids.items()):
        if not is_our_server(port):
            print("  Port %d (PID %d): not our server, left alone." % (port, pid))
            continue
        r = subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print("  Port %d (PID %d): old server stopped." % (port, pid))
            killed += 1
        else:
            print("  Port %d (PID %d): could not stop (%s)"
                  % (port, pid, (r.stderr or r.stdout).strip()[:80]))
    if killed == 0:
        print("  No stale server needed stopping.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
