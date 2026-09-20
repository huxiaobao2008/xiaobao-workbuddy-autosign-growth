# -*- coding: utf-8 -*-
"""全账号会话大清理（用户 2026-09-21 明确授权）：

- 所有账号的会话都是这几天自动化跑任务留下的遗留物，全部删除；
- 唯一保留：乡下人(account_e)上「与用户的当前对话」（正在使用中的会话，
  delete_conversation 本身就删不掉它，天然受保护）；
- 跑完所有账号后切回 account_e。

用法：python _mass_clean_convs.py [account_key ...]   # 缺省=全部启用账号
"""
import sys
import time

import account_switch as AS
import auto_buddy as core
import batch_runner as BR
import ui_driver as U

LOG = open("logs/_mass_clean.log", "a", encoding="utf-8")


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    LOG.write(line + "\n")
    LOG.flush()


def switch_and_wait(key):
    """切到指定账号并等侧边栏加载完成。

    坑（2026-09-21 实测）：① 不 reload 时客户端常"文件与界面都没指向目标账号"；
    ② 切完立刻读标题会读到空列表（侧边栏还没渲染），导致"删 0 条"的假象。
    所以：先 reload 切换，失败重试一次，再等列表出现（最多 15s）。
    """
    sw = AS.switch_to(key, reload=True, verify=True)
    if not sw.get("ok"):
        time.sleep(3)
        sw = AS.switch_to(key, reload=True, verify=True)
    if not sw.get("ok"):
        return sw, []
    titles = []
    for _ in range(10):
        time.sleep(1.5)
        titles = U.task_titles() or []
        if titles:
            break
    return sw, titles


def clean_account(key):
    """清空指定账号的任务会话。返回 (删除数, 剩余数)。

    ⚠️ 守卫：**当前正在打开的会话不许删**——2026-09-21 实测 in-use 保护并不可靠，
    mass 清理把用户正在使用的对话也删了。删除前读一次活动会话标题并跳过。
    """
    def active_title():
        try:
            return U.js("""(() => {
              const el = document.querySelector('[class*="active"]');
              if (el) return ((el.innerText || '') + '').trim().slice(0, 40) || null;
              return null;
            })()""", timeout=15)
        except Exception:
            return None

    protected = {x for x in [active_title()] if x}
    removed_total = 0
    for round_i in range(6):  # 删一批会露出更早的，循环到删不动为止
        titles = U.task_titles() or []
        if not titles:
            break
        removed = 0
        for t in titles:
            t = (t or "").strip()
            if not t:
                continue
            if any(p and (p in t or t in p) for p in protected):
                continue  # 正在使用的会话 → 跳过
            try:
                U.delete_conversation(t, force=False)
                removed += 1
                removed_total += 1
            except Exception:
                pass  # 受保护/使用中 → 本轮留着
            time.sleep(0.8)
        log("  [%s] 第 %d 轮删除 %d 条（累计 %d，剩余可见 %d）"
            % (key, round_i + 1, removed, removed_total, len(U.task_titles() or [])))
        if removed == 0:
            break
        time.sleep(2)
    left = len(U.task_titles() or [])
    return removed_total, left


def main():
    cfg = core.load_config()
    force = "--force" in sys.argv
    keys = [k for k in (sys.argv[1:] or [
        a["key"] for a in (cfg.get("accounts") or []) if a.get("enabled", True)])
        if k != "--force"]
    log("开始全账号清理（force=%s），账号：%s" % (force, ", ".join(keys)))
    total = 0
    restore_key = None
    try:
        restore_key = AS.current_key()[0]
        log("当前登录账号 %s（结束后切回）" % restore_key)
    except Exception:
        pass

    for key in keys:
        acc = next((a for a in (cfg.get("accounts") or []) if a.get("key") == key), None)
        if not acc:
            log("[%s] 配置里没有该账号 → 跳过" % key)
            continue
        # 闸：默认只在「任务全部完成 + 无可领积分」后才清（用户 2026-09-21 规则）；
        #     --force 才是用户明确授权的手动全清（今天用过一次）。
        if not force:
            ready, why = BR.account_ready_for_cleanup(acc, cfg)
            if not ready:
                log("[%s] 跳过清理：%s（要强清请加 --force）" % (key, why))
                continue
        try:
            sw, titles0 = switch_and_wait(key)
            if not sw.get("ok"):
                log("[%s] 切号失败：%s → 跳过" % (key, sw.get("err")))
                continue
            log("[%s] 已切换（界面=%s），可见会话 %d 条"
                % (key, (sw.get("after") or {}).get("menu"), len(titles0)))
            n, left = clean_account(key)
            total += n
            log("[%s] 清理完成：删除 %d 条，剩余 %d" % (key, n, left))
        except Exception as e:
            log("[%s] 异常：%s: %s" % (key, type(e).__name__, str(e)[:100]))

    back = restore_key or "account_e"
    try:
        AS.switch_to(back, reload=False, verify=True)
        log("已切回 %s" % back)
    except Exception as e:
        log("切回 %s 失败：%s" % (back, str(e)[:80]))
    log("全部完成，共删除 %d 条会话" % total)


if __name__ == "__main__":
    main()
