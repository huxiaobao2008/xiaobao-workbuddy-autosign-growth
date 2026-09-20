#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WorkBuddy 客户端「切换登录账号」（供 UI 驱动成长任务用）

为什么需要：UI 驱动只能作用于客户端**当前登录**的那个账号。
要给 6 个账号都刷成长任务，就得先把客户端切到目标账号。

做法（照搬 WorkDaddy 已验证的路径，见 research/WorkDaddy/scripts/lib.js:switchTo）：
  1) 备份当前登录文件
  2) 把目标账号的 {auth, account} 拼成官方 workbuddy-desktop.info 结构
  3) **原子替换**登录文件（写 .tmp → os.replace → chmod 600）
  4) 走 CDP 发 `Page.reload` 让渲染进程重新读取（**不重启客户端**）
  5) 从 `.user-menu-trigger` 读回昵称校验

登录文件：%LOCALAPPDATA%\\CodeBuddyExtension\\Data\\Public\\auth\\workbuddy-desktop.info

用法：
    python account_switch.py --list              # 客户端当前登录谁 + 可切换清单
    python account_switch.py --to account_b      # 切到 account_b（自动备份+校验）
    python account_switch.py --restore           # 回滚到最近一次切换前的备份
    python account_switch.py --backups           # 列出已保存的登录文件备份

注意：这是**改用户客户端的登录态**。所有写操作前都会先备份，且切换前会校验 uid。
"""
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auto_buddy as core   # noqa: E402
import cdp as C             # noqa: E402

AUTH_DIR = core.AUTH_DIR
LIVE = core.CURRENT_AUTH
BACKUP_DIR = os.path.join(core.BASE_DIR, "logs", "auth_backups")


# --------------------------------------------------------------------------- #
# 读
# --------------------------------------------------------------------------- #
def read_live():
    try:
        with open(LIVE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"__error__": str(e)}


def page_account(timeout=25):
    """读界面上的当前账号。

    注意：URL 里的 accountSnapshot 是**页面加载时**生成的，切换账号不会更新它
    （不 reload 的切换路径），所以校验一律以左下角 `.user-menu-trigger` 的昵称为准。
    `uid` 只作为参考，标了 stale 提示。
    """
    expr = """(function(){
      var out = { stale: true };
      try {
        var m = location.href.match(/accountSnapshot=([^&]+)/);
        if (m) { var o = JSON.parse(decodeURIComponent(decodeURIComponent(m[1]))); out.urlUid = o.uid || null; }
      } catch (e) { out.snapErr = String(e); }
      var el = document.querySelector('.user-menu-trigger');
      out.menuName = el ? (el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 80) : null;
      out.ready = !!document.querySelector('.conversation-sidebar');
      return out;
    })()"""
    cdp, _ = C.connect()
    try:
        return cdp.evaluate(expr, timeout=timeout)
    finally:
        cdp.close()


def page_uid(timeout=25):
    a = page_account(timeout)
    return (a or {}).get("urlUid")


def menu_matches(menu_name, want_nick):
    """菜单昵称是否就是目标账号（昵称可能被截断，双向包含判断）。"""
    if not menu_name or not want_nick:
        return False
    m = menu_name.strip()
    w = want_nick.strip()
    return m == w or m in w or w in m


def current_key():
    """客户端当前登录账号在 config 里的 key（按菜单昵称匹配，不依赖过期的 URL）。"""
    cur = page_account() or {}
    menu = cur.get("menuName")
    cfg = core.load_config()
    for a in cfg.get("accounts") or []:
        if menu_matches(menu, a.get("nickname") or ""):
            return a.get("key"), menu
    return None, menu


def wait_menu(want_nick, max_sec=12):
    """轮询等界面昵称变成目标账号。

    踩过的坑：连续快速切换时，左下角菜单的昵称不是立刻重绘的，
    写入后马上读会读到**上一个账号**的昵称，从而误判「切换失败」。
    所以校验必须是「轮询等待」，不是「读一次就下结论」。
    """
    t0 = time.time()
    last = None
    while time.time() - t0 < max_sec:
        try:
            a = page_account(timeout=10)
            last = a
            if menu_matches((a or {}).get("menuName"), want_nick or ""):
                return a
        except Exception:
            pass
        time.sleep(1.0)
    return last


def wait_ready(max_sec=60):
    """等页面重新可用（reload 之后）。"""
    t0 = time.time()
    while time.time() - t0 < max_sec:
        try:
            a = page_account(timeout=10)
            if a and a.get("ready"):
                return a
        except Exception:
            pass
        time.sleep(1.5)
    return None


def reload_page():
    """CDP Page.reload；断开后重连由调用方处理。"""
    cdp, _ = C.connect()
    try:
        cdp.call("Page.reload", {"ignoreCache": False}, timeout=20)
        return {"ok": True}
    except Exception as e:
        # reload 会让连接抖动，报错也可能已经生效
        return {"ok": True, "note": "reload 调用返回 %s（通常无碍）" % e}
    finally:
        try:
            cdp.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# 备份
# --------------------------------------------------------------------------- #
def backup_live(tag="auto", force=False):
    """备份当前登录文件；返回备份路径。tag=auto 时同名只留最新一份由调用方决定。"""
    if not os.path.exists(LIVE):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    cur = read_live()
    uid = ((cur.get("account") or {}).get("uid") or "unknown")[:8]
    ts = time.strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(BACKUP_DIR, "auth_%s_%s_%s.info" % (ts, uid, tag))
    if force or not os.path.exists(dest):
        shutil.copy2(LIVE, dest)
    # 固定名：给 --restore 用（每次切换前覆盖）
    if tag == "preswitch":
        shutil.copy2(LIVE, os.path.join(BACKUP_DIR, "auth_preswitch.info"))
    return dest


def list_backups():
    if not os.path.isdir(BACKUP_DIR):
        return []
    out = []
    for n in sorted(os.listdir(BACKUP_DIR), reverse=True):
        p = os.path.join(BACKUP_DIR, n)
        try:
            d = json.load(open(p, encoding="utf-8"))
            acct = d.get("account") or {}
            out.append({"file": n, "uid": acct.get("uid"), "nickname": acct.get("nickname"),
                        "size": os.path.getsize(p)})
        except Exception as e:
            out.append({"file": n, "error": str(e)})
    return out


# --------------------------------------------------------------------------- #
# 写
# --------------------------------------------------------------------------- #
def build_content(target_acct, target_auth, live):
    """拼成官方 {account, auth, accounts, allAccounts} 结构。

    accounts / allAccounts 按 uid 去重合并（与 WorkDaddy buildSeamlessAuthFile 一致）。
    """
    others = []
    seen_uids = set()
    for src in list(live.get("accounts") or []) + list(live.get("allAccounts") or []):
        if isinstance(src, dict) and src.get("uid") and src["uid"] != target_acct.get("uid"):
            # 按 uid 去重：`src not in others` 按整对象值相等判断，同 uid 字段略有差异会漏去重
            if src["uid"] not in seen_uids:
                seen_uids.add(src["uid"])
                others.append(src)
    acct = dict(target_acct)
    acct["lastLogin"] = True
    all_accs = others + [acct]
    return {"account": acct, "auth": dict(target_auth),
            "accounts": all_accs, "allAccounts": all_accs}


def atomic_write(path, obj):
    tmp = path + ".wbswitch.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 动作
# --------------------------------------------------------------------------- #
def switch_to(key, reload=True, verify=True, verify_max_sec=None):
    cfg = core.load_config()
    acct = next((a for a in cfg.get("accounts") or [] if a.get("key") == key), None)
    if not acct:
        return {"ok": False, "err": "配置里没有账号 %s" % key}

    before = page_account()
    out = {"target": key, "want_uid": acct.get("uid"),
           "before": {"page_uid": (before or {}).get("urlUid"),
                      "menu": (before or {}).get("menuName")}}

    # page_account() 返回的键是 urlUid（且切换前可能过期），不能用 "uid" 判断；
    # 「已在该账号」以左下角界面昵称为准（与 wait_menu 的校验口径一致）。
    if menu_matches((before or {}).get("menuName"), acct.get("nickname") or ""):
        out["ok"] = True
        out["switched"] = False
        out["msg"] = "客户端已经是该账号，无需切换"
        return out

    cred, err = core.load_cred(acct)
    if err:
        out["ok"] = False
        out["err"] = "目标账号凭证不可用：%s" % err
        return out

    # 校验：凭证里的 uid 必须与配置一致
    cred_uid = (cred.get("account") or {}).get("uid")
    if cred_uid != acct.get("uid"):
        out["ok"] = False
        out["err"] = "凭证 uid 与配置不符（凭证=%s 配置=%s），已中止" % (cred_uid, acct.get("uid"))
        return out
    if not (cred.get("auth") or {}).get("accessToken"):
        out["ok"] = False
        out["err"] = "目标账号缺少 accessToken"
        return out

    live = read_live()
    if live.get("__error__"):
        out["ok"] = False
        out["err"] = "读取登录文件失败：%s" % live["__error__"]
        return out

    out["backup"] = backup_live("preswitch", force=True)
    content = build_content(cred.get("account") or {}, cred.get("auth") or {}, live)
    atomic_write(LIVE, content)
    out["written"] = LIVE
    out["wrote_uid"] = content["account"].get("uid")

    if reload:
        out["reload"] = reload_page()
        time.sleep(2.0)
    if verify:
        # 实测：客户端每次请求都重读登录文件，所以不 reload 也会立刻生效。
        # 但界面昵称（左下角 .user-menu-trigger）的重绘有延迟——窗口隐藏 / 快速连续
        # 切换时尤其明显，单次读取会误判成「没切换」而报错。
        # 因此：先轮询等界面昵称；若界面一时没刷出来，**回退到登录文件 uid 这个权威依据**
        # ——文件一旦写对，客户端下一次请求就会用新账号，界面几秒内必跟上。
        # 这样「切没切」以文件为准，绝不会因为界面重绘慢而误报失败。
        max_sec = verify_max_sec or (20 if reload else 15)
        if reload:
            wait_ready(30)
            after = wait_menu(acct.get("nickname") or "", max_sec=max_sec)
        else:
            after = wait_menu(acct.get("nickname") or "", max_sec=max_sec)
        menu_ok = menu_matches((after or {}).get("menuName"), acct.get("nickname") or "")
        file_ok = (read_live().get("account") or {}).get("uid") == acct.get("uid")
        out["after"] = {"page_uid": (after or {}).get("urlUid"),
                        "menu": (after or {}).get("menuName"),
                        "menu_ok": menu_ok, "file_ok": file_ok}
        if menu_ok:
            out["ok"] = True
        elif file_ok:
            # 文件已切换成功，只是界面昵称还没重绘 —— 仍算成功，提示用户稍等刷新
            out["ok"] = True
            out["menu_pending"] = True
            out["msg"] = ("登录文件已切换到 %s，界面昵称可能稍后（几秒内）才刷新；"
                          "如长时间未变，点页面刷新或双击 restart-cdp.cmd 重启客户端。"
                          % acct.get("nickname"))
        else:
            out["ok"] = False
            out["err"] = ("切换后文件与界面都未指向目标账号（界面=%r 目标=%r）。"
                          "可双击 restore-main-account.cmd 回到主号，或重试。"
                          % ((after or {}).get("menuName"), acct.get("nickname")))
        return out
    out["ok"] = True
    return out


def restore():
    """把最近一次切换前的备份写回登录文件并 reload。"""
    src = os.path.join(BACKUP_DIR, "auth_preswitch.info")
    if not os.path.exists(src):
        return {"ok": False, "err": "没有 preswitch 备份，无法回滚"}
    with open(src, encoding="utf-8") as f:
        obj = json.load(f)
    uid = (obj.get("account") or {}).get("uid")
    atomic_write(LIVE, obj)
    out = {"ok": True, "restored_uid": uid, "from": src}
    out["reload"] = reload_page()
    time.sleep(2.0)
    after = wait_ready(60)
    # 校验以登录文件 uid 为权威（wait_ready 返回 page_account 结构，键是 urlUid/menuName，
    # 用 .get("uid") 恒为 None —— 老写法永远误报 ok=False）
    file_ok = (read_live().get("account") or {}).get("uid") == uid
    out["after"] = {"page_uid": (after or {}).get("urlUid"),
                    "menu": (after or {}).get("menuName"),
                    "file_ok": file_ok}
    out["ok"] = file_ok
    return out


def list_accounts():
    cfg = core.load_config()
    cur = page_account()
    cur_menu = (cur or {}).get("menuName")
    rows = []
    for a in cfg.get("accounts") or []:
        cred, err = core.load_cred(a)
        exp = None
        if not err:
            exp = core.cred_expiry_days(cred)
        rows.append({
            "key": a.get("key"), "label": a.get("label"), "uid": a.get("uid"),
            "nickname": a.get("nickname"),
            "cred_ok": not err, "cred_err": err or "",
            "days_left": round(exp, 1) if exp is not None else None,
            "is_current": menu_matches(cur_menu, a.get("nickname") or ""),
        })
    return {"page": cur, "accounts": rows}


def main():
    argv = sys.argv[1:]
    if not argv or "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0

    if "--list" in argv:
        r = list_accounts()
        p = r["page"] or {}
        print("客户端当前登录：%s  (urlUid=%s, 该值可能过期)" % (p.get("menuName"), p.get("urlUid")))
        print()
        print("%-11s %-14s %-8s %-10s %s" % ("key", "label", "凭证", "剩余天数", "UID"))
        print("-" * 78)
        for a in r["accounts"]:
            mark = "  ← 当前" if a["is_current"] else ""
            print("%-11s %-14s %-8s %-10s %s%s" % (
                a["key"], str(a["label"])[:13],
                "OK" if a["cred_ok"] else "不可用",
                a["days_left"] if a["days_left"] is not None else "-",
                a["uid"], mark))
            if not a["cred_ok"]:
                print("            ! %s" % a["cred_err"])
        return 0

    if "--backups" in argv:
        for b in list_backups():
            print("%-52s %-38s %s" % (b.get("file"), b.get("uid"), b.get("nickname")))
        return 0

    if "--restore" in argv:
        print(json.dumps(restore(), ensure_ascii=False, indent=2))
        return 0

    if "--to" in argv:
        i = argv.index("--to")
        if i + 1 >= len(argv):
            print("用法：--to <账号key> [--no-reload]")
            return 1
        r = switch_to(argv[i + 1], reload="--no-reload" not in argv,
                      verify="--no-verify" not in argv)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 1

    if "--write-only" in argv:
        i = argv.index("--write-only")
        if i + 1 >= len(argv):
            print("用法：--write-only <账号key>")
            return 1
        r = switch_to(argv[i + 1], reload=False, verify=False)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 1

    if "--who" in argv:
        print(json.dumps(page_account(), ensure_ascii=False, indent=2))
        return 0

    print("未知参数，见 --help")
    return 1


if __name__ == "__main__":
    sys.exit(main())
