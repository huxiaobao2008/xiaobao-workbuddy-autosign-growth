#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多账号 UI 任务编排器

解决问题：UI 驱动只能作用于客户端**当前登录**的账号，所以要多账号刷成长任务，
必须「切换账号 → 驱动 UI → 领取 → 切回」。

**必须整条命令一次跑完**：切换账号会改变客户端用的 token，而我自己（这个会话）
也跑在同一个客户端里 —— 中途插入别的操作有被打断的风险。一条命令跑完，
返回时客户端已经切回原账号，对我自己零影响。

用法：
    python ui_runner.py --account account_b \
        --templates 幻灯片,产品管理,深度研究 --code template_5
    python ui_runner.py --account account_e --templates 幻灯片,产品管理,深度研究,金融服务,个人工作台 --code template_5

参数：
    --account   目标账号 key（config.json 里的 key）
    --templates 逗号分隔的模板名，按序跑，跑到 --code 达标就停
    --code      目标任务 code，默认 template_5
    --no-claim  跑完不领取
    --keep      跑完不删会话（默认跑完即删）
    --stay      跑完不切回原账号（默认切回）
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auto_buddy as core     # noqa: E402
import tasks as T             # noqa: E402
import account_switch as AS   # noqa: E402
import ui_driver as U         # noqa: E402


def progress_of(key, code):
    """查某个账号某个任务的进度 -> (current, target, status)。"""
    cfg = core.load_config()
    acct = next((a for a in cfg["accounts"] if a["key"] == key), None)
    cred, err = core.load_cred(acct)
    if err:
        return None, None, "cred_err:" + err
    lst, err = T.fetch_tasks(cred, cfg)
    if err:
        return None, None, "fetch_err:" + err
    t = next((x for x in lst if x["code"] == code), None)
    if not t:
        return None, None, "not_found"
    return (t["progress"] or {}).get("current"), (t["progress"] or {}).get("target"), t["status"]


def current_key():
    """客户端当前登录账号在 config 里的 key（按菜单昵称判定，URL uid 会过期）。"""
    key, menu = AS.current_key()
    return key, menu


def main():
    argv = sys.argv[1:]

    def opt(name, default=None):
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                return argv[i + 1]
        return default

    key = opt("--account")
    if not key:
        print(__doc__)
        return 1
    code = opt("--code", "template_5")
    templates = [x for x in (opt("--templates", "") or "").split(",") if x]
    do_claim = "--no-claim" not in argv
    keep = "--keep" in argv
    stay = "--stay" in argv

    out = {"account": key, "code": code, "templates": templates, "steps": []}

    main_key, main_menu = current_key()
    out["main"] = {"key": main_key, "menu": main_menu}
    print("客户端当前账号：%s (界面昵称=%s)" % (main_key, main_menu))
    print("目标账号：%s   目标任务：%s   模板：%s" % (key, code, templates))

    # 1) 切换（不 reload：客户端每次请求都重读登录文件，reload 会打断当前会话）
    sw = AS.switch_to(key, reload=False)
    out["switch"] = sw
    print("\n[1] 切换 -> %s" % json.dumps(sw, ensure_ascii=False))
    if not sw.get("ok"):
        print("!! 切换失败，中止")
        return 1

    try:
        # 2) 逐个模板跑，跑到目标达标为止
        for i, tpl in enumerate(templates, 1):
            cur, tgt, status = progress_of(key, code)
            print("\n[2.%d] 目标进度 %s/%s (%s)" % (i, cur, tgt, status))
            if cur is not None and tgt and cur >= tgt:
                print("    已达标，停止跑模板")
                break
            print("    跑模板「%s」..." % tpl, flush=True)
            t0 = time.time()
            r = U.run_task(tpl, U.TEMPLATE_PROMPTS.get(tpl) or "用一句话回答即可。",
                           model=U.pick_model_for(code), max_wait=300,
                           delete_after=not keep)
            out["steps"].append({"template": tpl, "ok": r.get("ok"),
                                 "secs": round(time.time() - t0, 1),
                                 "created": r.get("created_title"),
                                 "deleted": (r.get("deleted") or {}).get("ok")})
            print("    结果 ok=%s 用时%.0fs 建了「%s」删除=%s"
                  % (r.get("ok"), time.time() - t0, r.get("created_title"),
                     (r.get("deleted") or {}).get("ok")), flush=True)
            if not r.get("ok"):
                print("    ! 该次未完成，继续下一个模板")

        cur, tgt, status = progress_of(key, code)
        out["final_progress"] = {"current": cur, "target": tgt, "status": status}
        print("\n[3] 最终进度 %s/%s (%s)" % (cur, tgt, status))

        # 3) 领取
        if do_claim:
            cfg = core.load_config()
            acct = next((a for a in cfg.get("accounts") or [] if a.get("key") == key), None)
            if acct:
                print("\n[4] 领取（接取 + 领取全部可领）...")
                res = T.run_account_tasks(acct, cfg)
                out["claim"] = res
                print("    %s" % json.dumps(res, ensure_ascii=False)[:600])
            else:
                print("    ! 配置里没有账号 %s，跳过领取" % key)
    finally:
        # 4) 切回原账号（无论成败）
        if not stay and main_key and main_key != key:
            back = AS.switch_to(main_key, reload=False)
            out["switch_back"] = back
            print("\n[5] 切回 %s -> ok=%s 界面=%s"
                  % (main_key, back.get("ok"), (back.get("after") or {}).get("menu")))
        else:
            print("\n[5] 未切回（stay 或已同账号）")

    print("\n=== 汇总 ===")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
