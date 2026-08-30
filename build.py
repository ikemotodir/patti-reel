# -*- coding: utf-8 -*-
# ============================================================
# 販売ページのビルダー
# ------------------------------------------------------------
# やること:
#   ① サンプル動画から代表コマを抜き、JPEGに縮めて販売ページへ焼き込む
#   ② 決済リンクを購入ボタンに差し込む
#   ③ 受付ページに「3つ書いて送る」メールボタンを差し込む
#
# 画像を外部ファイルにしないのは、1枚のHTMLで完結させるため
# （どこに置いてもリンク切れが起きない）。
#
#   python site/build.py
#   python site/build.py --buy-url "https://buy.stripe.com/xxx" --contact-email "you@example.com"
# ============================================================
import argparse
import base64
import glob
import os
import subprocess
import sys
import tempfile
import urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(BASE, "site")

# 5つのシーンの代表時刻（秒）
MARKS = [2.5, 8.5, 16.5, 22.5, 28.5]
WIDTH = 324           # 9:16 の縮小幅。ページ上の表示は最大 9.3rem ≒ 149px なので2倍
QUALITY = 5           # ffmpeg の -q:v（2が最高〜31が最低）

NL = chr(10)          # 本文の改行。エスケープを書かないで済むようにしている


def latest_render() -> str:
    hits = sorted(
        glob.glob(os.path.join(BASE, "works", "*", "renders", "*.mp4")),
        key=os.path.getmtime, reverse=True,
    )
    if not hits:
        raise SystemExit("サンプル動画が見つかりません。先に render してください。")
    return hits[0]


def grab(video: str, sec: float, out: str) -> None:
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(sec), "-i", video,
           "-frames:v", "1", "-vf", "scale=%d:-2" % WIDTH, "-q:v", str(QUALITY), out]
    subprocess.run(cmd, check=True)


def mail_body() -> str:
    """お客さんのメールソフトに出る下書き。埋めるだけで送れる形にしておく。"""
    lines = [
        "STUDIO PATTI 御中",
        "",
        "縦動画の制作をお願いします。",
        "",
        "--------------------------------",
        "1. 伝えたいこと（箇条書きで結構です）",
        "　",
        "　",
        "",
        "2. 見た人にどうなってほしいか",
        "　",
        "",
        "3. 使ってほしい素材のリンク（無ければ空欄で結構です）",
        "　",
        "--------------------------------",
        "",
        "お支払いに使ったメールアドレス：",
        "　",
        "",
    ]
    return NL.join(lines)


def build_send_block(contact_email):
    """受付ページの送信ブロックと連絡先表記を作る。"""
    if not contact_email:
        send = (
            '<div class="sendbox">'
            '<span class="k">連絡先メール未設定</span>'
            '<p>ここに「3つ書いて送る」ボタンが入ります。'
            '<code>--contact-email</code> でアドレスを渡すと差し込まれます。</p>'
            '<p>公開前に必ず設定してください。ここが空のままだと、'
            '買った人が素材の送り先を失います。</p>'
            '<p style="margin-top:1rem">'
            '<span class="sendbtn is-pending">3つ書いて送る（未設定）</span></p>'
            '</div>'
        )
        contact = '<span style="color:var(--shu);font-weight:600">要記入</span>'
        return send, contact, True

    mailto = "mailto:%s?subject=%s&body=%s" % (
        contact_email,
        urllib.parse.quote("【縦動画】素材と内容の送付"),
        urllib.parse.quote(mail_body()),
    )
    send = (
        '<div class="sendbox">'
        '<span class="k">押すだけで、下書きが開きます</span>'
        '<p>お使いのメールソフトが立ち上がり、上の3項目が入った下書きが出ます。'
        '埋めて送信してください。<strong>入力はそれで終わりです。</strong></p>'
        '<p style="margin-top:1rem">'
        '<a class="sendbtn" href="%s">3つ書いて送る</a></p>'
        '<p class="after">届いた時点から3営業日です。'
        'こちらから確認の返信をお送りします。</p>'
        '</div>' % mailto
    )
    contact = '<a href="mailto:%s">%s</a>' % (contact_email, contact_email)
    return send, contact, False


def main() -> int:
    ap = argparse.ArgumentParser(description="販売ページを1枚のHTMLに組み立てる")
    ap.add_argument("--video", default=None)
    ap.add_argument("--template", default=os.path.join(SITE, "index.template.html"))
    ap.add_argument("--out", default=os.path.join(SITE, "index.html"))
    ap.add_argument("--buy-url", default=None,
                    help="お試し(¥19,800)の決済リンク。未指定なら購入ボタンは「準備中」の見た目になる")
    ap.add_argument("--buy-url-single", default=None,
                    help="単発(¥49,800)の決済リンク")
    ap.add_argument("--contact-email", default=None,
                    help="お客さんからの連絡を受けるメールアドレス")
    args = ap.parse_args()

    video = args.video or latest_render()
    print("素材: %s" % os.path.relpath(video, BASE))

    with open(args.template, encoding="utf-8") as f:
        html = f.read()

    # ---- サンプルのコマを焼き込む ----
    tmp = tempfile.mkdtemp(prefix="patti_site_")
    total = 0
    for i, sec in enumerate(MARKS, 1):
        jpg = os.path.join(tmp, "f%d.jpg" % i)
        grab(video, sec, jpg)
        with open(jpg, "rb") as f:
            raw = f.read()
        total += len(raw)
        uri = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
        marker = "__FRAME%d__" % i
        if marker not in html:
            raise SystemExit("テンプレートに %s がありません" % marker)
        html = html.replace(marker, uri)
        print("  %s  t=%ss  %.1f KB" % (marker, sec, len(raw) / 1024))

    # ---- 決済リンク。未設定なら押せない見た目にする（リンク切れを出さない）----
    def put_link(doc, url, url_marker, state_marker):
        if url:
            return doc.replace(url_marker, url).replace(state_marker, ""), False
        doc = doc.replace('href="%s"' % url_marker, 'href="#" aria-disabled="true"')
        return doc.replace(state_marker, " is-pending"), True

    html, p1 = put_link(html, args.buy_url, "__BUY_URL__", "__BUY_STATE__")
    html, p2 = put_link(html, args.buy_url_single, "__BUY_URL2__", "__BUY2_STATE__")
    pending_buy = p1 or p2

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        f.write(html)

    # ---- 受付ページ ----
    # 受け取りはメール1通で完結させる。フォーム作成も通知設定も要らない分、
    # 公開までに人がやる作業が丸ごと1つ消える。
    pending_mail = False
    t_tpl = os.path.join(SITE, "thanks.template.html")
    t_out = os.path.join(SITE, "thanks.html")
    if os.path.isfile(t_tpl):
        with open(t_tpl, encoding="utf-8") as f:
            th = f.read()
        send, contact, pending_mail = build_send_block(args.contact_email)
        th = th.replace("__SEND_BLOCK__", send).replace("__CONTACT_PLAIN__", contact)
        with open(t_out, "w", encoding="utf-8", newline="") as f:
            f.write(th)
        print("出力: %s  %.0f KB%s" % (
            os.path.relpath(t_out, BASE), os.path.getsize(t_out) / 1024,
            "  ← 連絡先メール未設定" if pending_mail else ""))

    print("出力: %s  %.0f KB" % (os.path.relpath(args.out, BASE),
                                 os.path.getsize(args.out) / 1024))
    print("画像: %d 枚 / 元 %.0f KB" % (len(MARKS), total / 1024))

    if pending_buy or pending_mail:
        print()
        print("未設定があります。両方そろったら、これ1本で完成します:")
        print('  python site/build.py --buy-url "https://buy.stripe.com/xxx" '
              '--buy-url-single "https://buy.stripe.com/yyy" '
              '--contact-email "you@example.com"')
    else:
        print()
        print("すべて設定済み。公開できる状態です。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
