#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证「让路护栏」误判是否修好。

背景：驱动器自己会在页面里 dispatch 合成的 Escape keydown（关浮层），
以及用 CDP 派发真实按键。老代码把这些全算成「用户刚敲过键」，
于是同一个账号后面的任务集体误判让路（create_canvas / playbook_prompt 曾各丢 2 项）。

本脚本用**无害的 F13**（无默认行为）做三组对照，只看 __wbUserKey 会不会被推新：
  A. 页面内合成 keydown（isTrusted=false）  -> 期望 idleSec 不被重置
  B. CDP 派发按键 + driver_typing 置位      -> 期望 idleSec 不被重置
  C. CDP 派发按键 不置位（对照组）          -> 期望 idleSec 被重置（证明这条路真的会误伤）
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cdp as C          # noqa: E402
import ui_driver as U    # noqa: E402


def snap(tag):
    busy, st = U.user_busy(idle_sec=15)
    print("  %-42s idleSec=%-5s focused=%s  -> busy=%s"
          % (tag, st.get("idleSec"), st.get("focused"), busy))
    return st.get("idleSec")


def main():
    cdp, page = C.connect()
    print("[连接] ok")

    def key():
        cdp.call("Input.dispatchKeyEvent", {
            "type": "rawKeyDown", "key": "F13", "code": "F13",
            "windowsVirtualKeyCode": 124, "nativeVirtualKeyCode": 124}, timeout=15)

    # 基线：先让 watchdog 装上并确认「静置时 idleSec 会自然增长」
    a = snap("基线")
    time.sleep(4)
    b = snap("静置 4s 后（应 +4 左右）")

    # A) 页面内合成 keydown（isTrusted=false）——useTemplate 关浮层就是这么干的
    U.js("(() => { document.dispatchEvent(new KeyboardEvent('keydown',"
         " { key: 'Escape', bubbles: true })); return true; })()", timeout=20)
    c = snap("A 合成 Escape（期望：不被重置）")

    # B) CDP 真按键 + 置位
    U.driver_typing(True)
    key()
    U.driver_typing(False)
    d = snap("B CDP 按键 + driverTyping（期望：不被重置）")

    # C) 对照组：CDP 真按键、不置位。
    #    必须等过 driver_typing 留的 3s 时间窗，否则测的是「窗口还在起作用」，
    #    不是「真人按键能不能被识别」。
    time.sleep(3.5)
    c2 = snap("C 前（窗口已过期，应自然增长）")
    key()
    time.sleep(0.5)
    e = snap("C CDP 按键 不置位（期望：被重置到 ~0）")

    def verdict(name, before, after, want_reset):
        reset = (after is not None) and (after < 3)
        ok = (reset == want_reset)
        print("  [%s] %s（重置=%s 期望重置=%s）" % ("PASS" if ok else "FAIL",
                                                name, reset, want_reset))
        return ok

    print("\n== 判定 ==")
    ok = True
    ok &= verdict("A 合成事件不该算用户", b, c, False)
    ok &= verdict("B 置位的 CDP 按键不该算用户", c, d, False)
    ok &= verdict("C 未置位的 CDP 按键应算用户(对照组)", d, e, True)
    print("\n结论：%s" % ("全部符合预期，误判已修" if ok else "仍有不符，需继续查"))
    cdp.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
