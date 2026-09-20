#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a desktop .lnk shortcut to the Buddy Gas Station one-click launcher.

Uses ctypes + IShellLink (no WScript.Shell COM, which is blocked by policy).
"""
import ctypes
import uuid
import os
import struct
from ctypes import byref

ole32 = ctypes.windll.ole32


def gbuf(s):
    # Windows GUID: Data1/Data2/Data3 little-endian, Data4 as-is.
    u = uuid.UUID(s)
    b = struct.pack("<IHH", u.time_low, u.time_mid, u.time_hi_version) + u.bytes[8:16]
    return ctypes.create_string_buffer(b, 16)


ole32.CoInitialize.argtypes = [ctypes.c_void_p]
ole32.CoInitialize.restype = ctypes.HRESULT
ole32.CoCreateInstance.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p]
ole32.CoCreateInstance.restype = ctypes.HRESULT

PVOID = ctypes.c_void_p
LPWSTR = ctypes.c_wchar_p
HRESULT = ctypes.HRESULT

iface = PVOID(0)
ppv = PVOID(0)
hr = ole32.CoInitialize(None)
hr = ole32.CoCreateInstance(gbuf("{00021401-0000-0000-C000-000000000046}"), None, 1,
                           gbuf("{000214F9-0000-0000-C000-000000000046}"), byref(ppv))
if hr != 0:
    raise RuntimeError("CoCreateInstance failed hr=0x%x" % hr)

iface = ppv
vt = ctypes.cast(iface, ctypes.POINTER(PVOID))
VT = ctypes.POINTER(PVOID)
vtable = ctypes.cast(vt[0], VT)

SetPath = ctypes.CFUNCTYPE(HRESULT, PVOID, LPWSTR)(vtable[5])
SetWD = ctypes.CFUNCTYPE(HRESULT, PVOID, LPWSTR)(vtable[10])
SetDesc = ctypes.CFUNCTYPE(HRESULT, PVOID, LPWSTR)(vtable[8])
QI = ctypes.CFUNCTYPE(HRESULT, PVOID, ctypes.c_void_p, ctypes.c_void_p)(vtable[0])
Release = ctypes.CFUNCTYPE(ctypes.c_ulong, PVOID)(vtable[2])

TARGET = r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto\Buddy加油站一键执行.cmd"
WORKDIR = r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto"
DESC = "Buddy加油站 一键执行：签到+任务+领积分+出行"
LNK = r"C:\Users\Administrator\Desktop\Buddy加油站 一键执行.lnk"

hr = SetPath(iface, TARGET)
if hr != 0:
    raise RuntimeError("SetPath failed hr=0x%x" % hr)
hr = SetWD(iface, WORKDIR)
if hr != 0:
    raise RuntimeError("SetWorkingDirectory failed hr=0x%x" % hr)
hr = SetDesc(iface, DESC)
if hr != 0:
    raise RuntimeError("SetDescription failed hr=0x%x" % hr)

ipf = PVOID(0)
hr = QI(iface, gbuf("{0000010B-0000-0000-C000-000000000046}"), byref(ipf))
if hr != 0:
    raise RuntimeError("QueryInterface IPersistFile failed hr=0x%x" % hr)

ipf_vt = ctypes.cast(ipf, ctypes.POINTER(PVOID))
ipf_vtable = ctypes.cast(ipf_vt[0], VT)
Save = ctypes.CFUNCTYPE(HRESULT, PVOID, LPWSTR, ctypes.c_int)(ipf_vtable[6])
hr = Save(ipf, LNK, 1)
if hr != 0:
    raise RuntimeError("Save failed hr=0x%x" % hr)

Release(ipf)
Release(iface)
ole32.CoUninitialize()

print("OK shortcut ->", LNK, "| exists:", os.path.exists(LNK))
