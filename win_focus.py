"""把 WorkBuddy 客户端主窗口恢复并置前。

背景：窗口处于最小化/隐藏时，渲染进程 document.hidden=true：
  1) 定时器被重度节流（实测 sleep 慢 ~19 倍）→ CDP 调用必然超时；
  2) react-virtuoso 拿不到容器高度（h=0）→ 专家列表渲染 0 项。
所以做任何 UI 驱动之前，先确保窗口可见。

用 ctypes 直接调 Win32 API（bash 内禁止 powershell）。
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

user32 = ctypes.windll.user32

SW_RESTORE = 9
SW_SHOW = 5

EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def _text(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _cls(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def find_windows(needle="WorkBuddy"):
    found = []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            # 仍然记录隐藏窗口，后面要恢复它
            pass
        t = _text(hwnd)
        c = _cls(hwnd)
        if needle.lower() in (t or "").lower() or needle.lower() in (c or "").lower():
            found.append({"hwnd": hwnd, "title": t, "cls": c,
                          "visible": bool(user32.IsWindowVisible(hwnd)),
                          "iconic": bool(user32.IsIconic(hwnd))})
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return found


def restore(hwnd):
    before = {"visible": bool(user32.IsWindowVisible(hwnd)),
              "iconic": bool(user32.IsIconic(hwnd))}
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.ShowWindow(hwnd, SW_SHOW)
    try:
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.6)
    after = {"visible": bool(user32.IsWindowVisible(hwnd)),
             "iconic": bool(user32.IsIconic(hwnd))}
    return before, after


if __name__ == "__main__":
    needle = sys.argv[1] if len(sys.argv) > 1 else "WorkBuddy"
    wins = find_windows(needle)
    if not wins:
        print("没有找到标题/类名含 %r 的窗口" % needle)
        sys.exit(2)
    for w in wins:
        print("FOUND hwnd=%s cls=%r title=%r visible=%s iconic=%s"
              % (w["hwnd"], w["cls"], w["title"][:60], w["visible"], w["iconic"]))
    # 优先恢复「可见但最小化」或标题像主窗口的那些
    main = [w for w in wins if w["cls"] not in ("Chrome_WidgetWin_0",)]
    for w in (main or wins):
        b, a = restore(w["hwnd"])
        print("RESTORE hwnd=%s %s -> %s" % (w["hwnd"], b, a))
