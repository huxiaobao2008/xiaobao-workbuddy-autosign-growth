#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows 原生托盘气泡提醒（纯 ctypes 调用 Win32 API，不依赖 PowerShell、不依赖第三方库）。
用法：pythonw notify_toast.py "标题" "内容"
独立进程运行，不阻塞主程序；显示约 12 秒后自动消失。
"""
import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIIF_WARNING = 0x00000002
IDI_WARNING = 32515
WM_USER = 0x0400
PM_REMOVE = 0x0001

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, ctypes.c_uint,
                             wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256), ("uTimeout", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wintypes.HICON),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND), ("message", wintypes.UINT), ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM), ("time", wintypes.DWORD), ("pt", wintypes.POINT),
        ("lPrivate", wintypes.DWORD),
    ]


def def_window_proc(hwnd, msg, wparam, lparam):
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def show(title, text, seconds=12):
    wndproc = WNDPROC(def_window_proc)
    hinstance = kernel32.GetModuleHandleW(None)
    cls_name = "WorkBuddyAutoToastCls"
    wc = WNDCLASSW()
    wc.lpfnWndProc = wndproc
    wc.hInstance = hinstance
    wc.lpszClassName = cls_name
    user32.RegisterClassW(ctypes.byref(wc))  # 重复注册返回 0，忽略

    hwnd = user32.CreateWindowExW(0, cls_name, "BuddyAuto", 0, 0, 0, 0, 0,
                                  None, None, hinstance, None)
    if not hwnd:
        return False

    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = hwnd
    nid.uID = 1
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_INFO
    nid.uCallbackMessage = WM_USER + 1
    nid.hIcon = user32.LoadIconW(None, ctypes.cast(IDI_WARNING, wintypes.LPCWSTR))
    nid.szTip = "Buddy 自动任务"
    nid.szInfoTitle = title[:63]
    nid.szInfo = text[:255]
    nid.dwInfoFlags = NIIF_WARNING
    nid.uTimeout = seconds * 1000

    if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
        user32.DestroyWindow(hwnd)
        return False

    msg = MSG()
    end = time.time() + seconds
    while time.time() < end:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.1)

    shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
    user32.DestroyWindow(hwnd)
    return True


if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "Buddy 提醒"
    m = sys.argv[2] if len(sys.argv) > 2 else ""
    sys.exit(0 if show(t, m) else 1)
