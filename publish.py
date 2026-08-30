# -*- coding: utf-8 -*-
# ============================================================
# 組み直して公開する（publish.bat から呼ばれる）
# ------------------------------------------------------------
# 決済リンクやメールアドレスを毎回打たなくていいように、
# publish.config.json に置いた値を読んで build.py に渡す。
# ============================================================
import io
import json
import os
import subprocess
import sys

SITE = os.path.dirname(os.path.abspath(__file__))


def main():
    cfg_path = os.path.join(SITE, "publish.config.json")
    cfg = json.load(io.open(cfg_path, encoding="utf-8"))

    args = [sys.executable, os.path.join(SITE, "build.py")]
    for key, flag in [("buy_url", "--buy-url"),
                      ("buy_url_single", "--buy-url-single"),
                      ("contact_email", "--contact-email")]:
        v = cfg.get(key)
        if v:
            args += [flag, v]

    print("組み立てています…")
    if subprocess.run(args).returncode != 0:
        print("組み立てに失敗しました。公開は中止します。")
        return 1

    st = subprocess.run(["git", "status", "--porcelain"], cwd=SITE,
                        capture_output=True, text=True, encoding="utf-8")
    if not st.stdout.strip():
        print()
        print("変更がありません。公開するものはありません。")
        return 0

    print()
    print("変更:")
    for line in st.stdout.strip().split("\n"):
        print("  " + line)

    msg = " ".join(sys.argv[1:]).strip() or "ページを更新"
    for cmd in (["git", "add", "-A"],
                ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", msg],
                ["git", "push", "-q", "origin", "main"]):
        if subprocess.run(cmd, cwd=SITE).returncode != 0:
            print("失敗しました: " + " ".join(cmd))
            return 1

    print()
    print("公開しました → https://ikemotodir.github.io/patti-reel/")
    print("反映まで1分ほどかかります。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
