#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
极简 CDP 客户端（零第三方依赖，标准库实现 WebSocket + Chrome DevTools Protocol）

用途：连上 WorkBuddy 客户端自带的调试端口（环境变量 WORKBUDDY_REMOTE_DEBUGGING_PORT
开启，见 client_cdp.py），在渲染进程里执行 JS / 读取界面状态 / 驱动 UI。

为什么不用现成库：本项目约定零第三方依赖，且只跑在受管 Python 上；
CDP 只需要文本帧 + 请求响应，标准库 socket 足够，不必装 websocket-client。

用法：
    python cdp.py info                 # 列出可驱动页面
    python cdp.py eval "<js 表达式>"    # 在页面里求值（支持 await Promise）
    python cdp.py eval-file <js 文件>   # 从文件读 JS 求值
"""
import base64
import hashlib
import json
import os
import socket
import struct
import sys
import time
import urllib.request
from urllib.parse import urlparse

PORT = int(os.environ.get("WORKBUDDY_CDP_PORT", "9222"))
BASE_SHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
# 本机代理会把 127.0.0.1 也走代理，必须显式绕过
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

OP_TEXT, OP_BIN, OP_CLOSE, OP_PING, OP_PONG = 0x1, 0x2, 0x8, 0x9, 0xA


class CdpError(Exception):
    pass


# --------------------------------------------------------------------------- #
# 最小 WebSocket
# --------------------------------------------------------------------------- #
class WebSocket:
    def __init__(self, url, timeout=30.0):
        u = urlparse(url)
        if u.scheme != "ws":
            raise CdpError("只支持 ws:// 地址，收到 %s" % url)
        self.host = u.hostname
        self.port = u.port or 80
        self.path = (u.path or "/") + (("?" + u.query) if u.query else "")
        self.timeout = timeout
        self._buf = b""
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self.sock.settimeout(timeout)
        self._handshake()

    def _handshake(self):
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            "GET %s HTTP/1.1\r\n"
            "Host: %s:%d\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ) % (self.path, self.host, self.port, key)
        self.sock.sendall(req.encode())

        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CdpError("握手时连接被关闭")
            head += chunk
        head, rest = head.split(b"\r\n\r\n", 1)
        self._buf = rest
        status = head.split(b"\r\n", 1)[0].decode("latin-1")
        if not status.startswith("HTTP/1.1 101"):
            raise CdpError("握手失败：%s" % status)
        expect = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode().lower()
        got = ""
        for line in head.decode("latin-1").split("\r\n"):
            if line.lower().startswith("sec-websocket-accept:"):
                got = line.split(":", 1)[1].strip().lower()
        if got and got != expect:
            raise CdpError("Sec-WebSocket-Accept 校验失败")

    # ---------- 读 ----------
    def _read(self, n):
        while len(self._buf) < n:
            chunk = self.sock.recv(max(4096, n - len(self._buf)))
            if not chunk:
                raise CdpError("连接被对端关闭")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _read_frame(self):
        b0, b1 = self._read(2)
        fin = b0 & 0x80
        opcode = b0 & 0x0F
        masked = b1 & 0x80
        ln = b1 & 0x7F
        if ln == 126:
            ln = struct.unpack(">H", self._read(2))[0]
        elif ln == 127:
            ln = struct.unpack(">Q", self._read(8))[0]
        mask = self._read(4) if masked else None
        payload = self._read(ln) if ln else b""
        if mask:
            payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
        return bool(fin), opcode, payload

    def recv_text(self):
        """收一条完整文本消息；自动回应 ping、处理分片。"""
        chunks = []
        while True:
            fin, opcode, payload = self._read_frame()
            if opcode == OP_PING:
                self._send_frame(OP_PONG, payload)
                continue
            if opcode == OP_PONG:
                continue
            if opcode == OP_CLOSE:
                raise CdpError("收到关闭帧")
            if opcode in (OP_TEXT, OP_BIN):
                chunks = [payload]
            elif opcode == 0x0:          # continuation
                chunks.append(payload)
            else:
                continue
            if fin:
                return b"".join(chunks).decode("utf-8", "replace")

    # ---------- 写 ----------
    def _send_frame(self, opcode, payload):
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        header = bytearray([0x80 | opcode])
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < (1 << 16):
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        masked = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def send_text(self, s):
        self._send_frame(OP_TEXT, s)

    def close(self):
        try:
            self._send_frame(OP_CLOSE, b"")
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# CDP
# --------------------------------------------------------------------------- #
class CDP:
    def __init__(self, ws_url, timeout=30.0):
        self.ws = WebSocket(ws_url, timeout=timeout)
        self._id = 0
        self._events = []          # 未被 handler 消费的事件先存着
        self.handlers = {}

    def call(self, method, params=None, timeout=30.0):
        self._id += 1
        mid = self._id
        msg = {"id": mid, "method": method}
        if params:
            msg["params"] = params
        self.ws.send_text(json.dumps(msg))
        deadline = time.time() + timeout
        while True:
            remain = deadline - time.time()
            if remain <= 0:
                raise CdpError("%s 超时（%.0fs）" % (method, timeout))
            self.ws.sock.settimeout(max(0.5, remain))
            raw = self.ws.recv_text()
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            if obj.get("id") == mid:
                if "error" in obj:
                    raise CdpError("%s 返回错误：%s" % (method, obj["error"]))
                return obj.get("result") or {}
            if "method" in obj:                     # 事件
                h = self.handlers.get(obj["method"])
                if h:
                    try:
                        h(obj.get("params") or {})
                    except Exception:
                        pass
                else:
                    self._events.append(obj)

    def evaluate(self, expr, await_promise=True, return_by_value=True, timeout=30.0):
        r = self.call("Runtime.evaluate", {
            "expression": expr,
            "awaitPromise": await_promise,
            "returnByValue": return_by_value,
            "userGesture": True,
        }, timeout=timeout)
        if r.get("exceptionDetails"):
            d = r["exceptionDetails"]
            desc = (d.get("exception") or {}).get("description") or d.get("text")
            raise CdpError("JS 抛错：%s" % desc)
        return (r.get("result") or {}).get("value")

    def close(self):
        self.ws.close()


# --------------------------------------------------------------------------- #
# 目标发现
# --------------------------------------------------------------------------- #
def list_pages():
    r = _OPENER.open("http://127.0.0.1:%d/json/list" % PORT, timeout=5)
    return json.loads(r.read().decode("utf-8", "replace"))


def find_workbuddy_page(prefer_substr=None):
    pages = [p for p in list_pages() if p.get("type") == "page"]
    if not pages:
        raise CdpError("端口 %d 上没有可驱动的 page（客户端是否带调试端口启动？）" % PORT)
    if prefer_substr:
        for p in pages:
            if prefer_substr in (p.get("url") or ""):
                return p
    return pages[0]


def unhide(cdp):
    """把渲染进程的 visibilityState 强制拉回 visible（焦点模拟）。

    为什么必须做（2026-09-19 实战教训，血泪）：
    当客户端窗口被别的窗口完全遮挡、或远程会话断开/锁屏时，Chromium 会把页面
    判定为 hidden，后果非常隐蔽且致命：
      1) 定时器被重度节流 —— 实测页面内 sleep(2500) 实际跑了 47 秒（慢 ~19 倍），
         任何「在 JS 里等一等」的驱动脚本都会把等待放大成几百秒，CDP 必然超时；
      2) react-virtuoso 虚拟列表拿不到容器高度（.ec-expert-grid 高度 0）→
         专家列表渲染 0 项，看起来像「列表坏了 / 暂无内容」。
    这两种现象都非常容易被误判成「页面有 bug」，实际只是窗口不可见。

    注意：焦点模拟是**按 CDP 连接**生效的，而本项目每次操作都会新建连接，
    所以必须在 connect() 里设置，而不是手动设一次就完事。
    """
    try:
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True})
    except Exception:
        pass  # 老协议不支持就跳过，不影响原有流程
    return cdp


def connect(prefer_substr="app.asar/renderer"):
    p = find_workbuddy_page(prefer_substr)
    ws = p.get("webSocketDebuggerUrl")
    if not ws:
        raise CdpError("该页面没有 webSocketDebuggerUrl")
    return unhide(CDP(ws)), p


def find_target(url_substr=None, type_=None):
    """按 URL 子串 / 目标类型找调试目标（跨域 iframe 是独立类型 "iframe"）。"""
    for p in list_pages():
        if type_ and p.get("type") != type_:
            continue
        if url_substr and url_substr not in (p.get("url") or ""):
            continue
        if p.get("webSocketDebuggerUrl"):
            return p
    return None


def connect_target(url_substr=None, type_=None):
    p = find_target(url_substr, type_)
    if not p:
        raise CdpError("找不到调试目标 url~%r type=%r" % (url_substr, type_))
    return unhide(CDP(p["webSocketDebuggerUrl"])), p


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def screenshot(cdp, path, full=False):
    """截取页面，返回保存的字节数。"""
    params = {"format": "png"}
    if full:
        params["captureBeyondViewport"] = True
    r = cdp.call("Page.captureScreenshot", params, timeout=30)
    data = base64.b64decode(r.get("data") or "")
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]

    if cmd == "info":
        try:
            pages = list_pages()
        except Exception as e:
            print("无法访问 CDP 端口 %d：%s" % (PORT, e))
            return 2
        print("端口 %d 上共 %d 个目标：" % (PORT, len(pages)))
        for i, p in enumerate(pages):
            print("  [%d] %-12s %-20s %s" % (i, p.get("type"), (p.get("title") or "")[:20],
                                             (p.get("url") or "")[:100]))
        return 0

    if cmd == "shot":
        path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE_SHOT, "shot.png")
        cdp, page = connect()
        try:
            n = screenshot(cdp, path, full="--full" in sys.argv)
            print("已保存 %s（%d 字节）" % (path, n))
        finally:
            cdp.close()
        return 0

    if cmd in ("eval", "eval-file"):
        args = [a for a in sys.argv[2:] if not a.startswith("--")]
        tmo = 30.0
        for a in sys.argv:
            if a.startswith("--timeout="):
                tmo = float(a.split("=", 1)[1])
        if not args:
            print("缺少 JS 参数")
            return 1
        expr = args[0]
        if cmd == "eval-file":
            expr = open(expr, encoding="utf-8").read()
        cdp, page = connect()
        try:
            val = cdp.evaluate(expr, timeout=tmo)
            if isinstance(val, (dict, list)):
                print(json.dumps(val, ensure_ascii=False, indent=2))
            else:
                print(val)
        finally:
            cdp.close()
        return 0

    print("未知子命令：%s" % cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main())
