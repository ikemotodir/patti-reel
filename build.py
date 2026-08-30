# -*- coding: utf-8 -*-
# ============================================================
# 販売ページのビルダー
# ------------------------------------------------------------
# やること:
#   ① サンプル動画から代表コマを抜き、JPEGに縮めて販売ページへ焼き込む
#   ② 決済リンクを購入ボタンに差し込む
#   ③ ページ本文のFAQから構造化データ（JSON-LD）を組み立てる
#   ④ <!--HEAD--> を head に入れた完全なHTMLを書き出す
#   ⑤ 受付ページに「3つ書いて送る」メールボタンを差し込む
#
# 画像を外部ファイルにしないのは、1枚のHTMLで完結させるため
# （どこに置いてもリンク切れが起きない）。
#
#   python site/build.py
#   python site/build.py --buy-url "https://buy.stripe.com/xxx"
#                        --buy-url-single "https://buy.stripe.com/yyy"
#                        --contact-email "you@example.com"
# ============================================================
import argparse
import base64
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(BASE, "site")

SITE_URL = "https://ikemotodir.github.io/patti-reel/"

# 販売ページに載せるサンプル。works/<dir> の最新レンダーから、指定の秒数のコマを抜く。
# 増やすときはここに1行足して、テンプレートに __S3F1__.. のマーカーを置くだけ。
SAMPLES = [
    {"key": "S1", "dir": "sample-crop",    "marks": [2.5, 8.5, 16.5, 28.5]},
    {"key": "S2", "dir": "sample-recruit", "marks": [2.5, 8.5, 16.5, 28.5]},
    {"key": "S3", "dir": "sample-lunch",   "marks": [2.5, 8.5, 16.5, 28.5]},
]
WIDTH = 300           # 9:16 の縮小幅。表示は最大 9.3rem ≒ 149px なので2倍。
                      # 12枚をdata URIで埋めるとページが重くなるので、必要最小限に留める
QUALITY = 7           # ffmpeg の -q:v（2が最高〜31が最低）

NL = chr(10)          # 本文の改行。エスケープを書かないで済むようにしている


# ------------------------------------------------------------
# 素材
# ------------------------------------------------------------
def latest_render(work_dir="*"):
    hits = sorted(
        glob.glob(os.path.join(BASE, "works", work_dir, "renders", "*.mp4")),
        key=os.path.getmtime, reverse=True,
    )
    if not hits:
        raise SystemExit("サンプル動画が見つかりません（%s）。先に render してください。" % work_dir)
    return hits[0]


def grab(video, sec, out):
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(sec), "-i", video,
           "-frames:v", "1", "-vf", "scale=%d:-2" % WIDTH, "-q:v", str(QUALITY), out]
    subprocess.run(cmd, check=True)


# ------------------------------------------------------------
# 構造化データ
# ------------------------------------------------------------
def extract_faq(html):
    """
    ページに実際に出ているFAQを、そのまま構造化データにする。
    ここを手で書き写すと、片方だけ直したときに食い違う。だから必ず本文から取る。
    """
    # <dl class="faq"> のように属性が付くことがあるので [^>]* を入れる
    m = re.search(r"よくある質問.*?<dl[^>]*>(.*?)</dl>", html, re.S)
    if not m:
        return []
    pairs = re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", m.group(1), re.S)
    out = []
    for q, a in pairs:
        q = re.sub(r"<[^>]+>", "", q).strip()
        a = re.sub(r"<br\s*/?>", " ", a)
        a = re.sub(r"<[^>]+>", "", a).strip()
        a = re.sub(r"\s+", " ", a)
        if q and a:
            out.append({
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            })
    return out


def build_jsonld(html, buy_url, buy_url_single, contact_email):
    """
    検索とAI検索に「何を・いくらで・どこの誰が売っているか」を機械可読で渡す。
    2026年は検索の68%がゼロクリックなので、引用される形で置いておくことが効く。
    戻り値: (scriptタグの文字列, Offer数, FAQ数)
    """
    org = {
        "@type": "Organization",
        "@id": SITE_URL + "#org",
        "name": "合同会社スタジオパッチ",
        "alternateName": "STUDIO PATTI",
        "url": SITE_URL,
        "address": {
            "@type": "PostalAddress",
            "addressCountry": "JP",
            "addressRegion": "愛知県",
            "addressLocality": "一宮市",
            "streetAddress": "西五城中切29-1",
        },
    }
    if contact_email:
        org["email"] = contact_email

    plans = [
        ("縦動画 お試し1本（30秒まで）", "19800", buy_url,
         "30秒までの縦型ショート動画1本。修正1回込み。3営業日以内に納品。1社1回限り。"),
        ("縦動画 単発1本（60秒まで）", "49800", buy_url_single,
         "60秒までの縦型ショート動画1本。修正1回込み。3営業日以内に納品。"),
    ]
    offers = []
    for name, price, url, desc in plans:
        if not url:
            continue
        offers.append({
            "@type": "Offer",
            "name": name,
            "description": desc,
            "price": price,
            "priceCurrency": "JPY",
            "url": url,
            "availability": "https://schema.org/InStock",
            "seller": {"@id": SITE_URL + "#org"},
        })

    service = {
        "@type": "Service",
        "@id": SITE_URL + "#service",
        "name": "縦型ショート動画の制作代行",
        "serviceType": "動画制作",
        "provider": {"@id": SITE_URL + "#org"},
        "areaServed": {"@type": "Country", "name": "日本"},
        "url": SITE_URL,
        "description": ("縦型ショート動画（1080×1920 / 30fps / H.264）を固定価格で制作します。"
                        "見積もりも打ち合わせもなく、購入後に3項目を送るだけで、"
                        "3営業日以内にMP4を納品します。修正1回込み。"
                        "撮影・出演・ナレーション収録・投稿代行は含みません。"),
    }
    if offers:
        service["offers"] = offers

    graph = [org, service]
    faq = extract_faq(html)
    if faq:
        graph.append({"@type": "FAQPage", "@id": SITE_URL + "#faq", "mainEntity": faq})

    doc = {"@context": "https://schema.org", "@graph": graph}
    body = json.dumps(doc, ensure_ascii=False, indent=2)
    tag = '<script type="application/ld+json">' + NL + body + NL + "</script>"
    return tag, len(offers), len(faq)


def build_process_jsonld():
    """
    工程ページ用。HowTo で「どういう順番で作るか」を機械に渡す。
    AI検索は「打ち合わせなしで作れるのか」のような質問に答えるとき、
    手順が構造化されている文書を引きやすい。
    """
    steps = [
        ("読む", "送られた3項目をそのまま制作フォルダに置く。要約しない。"),
        ("決める", "30秒に入る情報は多くて3つ。何を捨てるかを決める。"),
        ("組む", "動画をHTMLとして書く。編集ソフトのタイムラインは触らない。"),
        ("検査する", "書き出す前に機械が検査する。タイムラインを何点かで切って、"
                    "その時刻の画面を1枚ずつ調べる。文字の被り・はみ出し・"
                    "コントラスト不足を検出し、1つでも引っかかったら書き出さない。"),
        ("書き出す", "1コマずつ描画してMP4にする。30秒で15〜25秒。"),
        ("見て、決める", "出てきた動画を人が見て、出すか直すかを決める。"),
    ]
    howto = {
        "@type": "HowTo",
        "@id": SITE_URL + "process.html#howto",
        "name": "縦型ショート動画を打ち合わせなしで3営業日以内に作る工程",
        "description": ("固定価格・打ち合わせなしで縦型ショート動画を制作する工程。"
                        "機械が検査する範囲と、人が判断する範囲を分けている。"),
        "totalTime": "P3D",
        "step": [
            {"@type": "HowToStep", "position": i, "name": n, "text": t}
            for i, (n, t) in enumerate(steps, 1)
        ],
    }
    page = {
        "@type": "WebPage",
        "@id": SITE_URL + "process.html",
        "url": SITE_URL + "process.html",
        "name": "打ち合わせなしで、なぜ作れるのか",
        "inLanguage": "ja",
        "isPartOf": {"@id": SITE_URL + "#org"},
        "about": {"@id": SITE_URL + "#service"},
    }
    crumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "縦動画を3営業日で",
             "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "制作工程",
             "item": SITE_URL + "process.html"},
        ],
    }
    doc = {"@context": "https://schema.org", "@graph": [page, howto, crumb]}
    return ('<script type="application/ld+json">' + NL
            + json.dumps(doc, ensure_ascii=False, indent=2) + NL + "</script>")


def build_price_jsonld(html):
    """
    相場ページ用。FAQPage と Article を渡す。
    「ショート動画 外注 相場」で来た人に答える文書なので、
    AI検索が価格の質問に答えるとき引きやすい形にしておく。
    """
    faq = extract_faq(html)
    article = {
        "@type": "Article",
        "@id": SITE_URL + "price.html#article",
        "headline": "ショート動画の外注、相場はいくらか",
        "description": ("ショート動画の外注費用を依頼先4タイプで比較し、"
                        "1本2,000円から月120万円までの幅が何によるのかを工程ごとに分解した記事。"),
        "inLanguage": "ja",
        "url": SITE_URL + "price.html",
        "author": {"@id": SITE_URL + "#org"},
        "publisher": {"@id": SITE_URL + "#org"},
        "about": {"@id": SITE_URL + "#service"},
    }
    crumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "縦動画を3営業日で", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "外注の相場",
             "item": SITE_URL + "price.html"},
        ],
    }
    graph = [article, crumb]
    if faq:
        graph.append({"@type": "FAQPage", "@id": SITE_URL + "price.html#faq",
                      "mainEntity": faq})
    doc = {"@context": "https://schema.org", "@graph": graph}
    return ('<script type="application/ld+json">' + NL
            + json.dumps(doc, ensure_ascii=False, indent=2) + NL + "</script>"), len(faq)


def split_head(html):
    """<!--HEAD--> ... <!--/HEAD--> を head 部と body 部に分ける。"""
    m = re.search(r"<!--HEAD-->(.*?)<!--/HEAD-->", html, re.S)
    if not m:
        return None, html
    head = m.group(1).strip()
    body = (html[:m.start()] + html[m.end():]).strip()
    return head, body


def wrap_document(head, body):
    """lang属性を正しく持った完全なHTMLにする（断片のままだと言語が未指定になる）。"""
    parts = ["<!doctype html>", '<html lang="ja">', "<head>", head, "</head>",
             "<body>", body, "</body>", "</html>", ""]
    return NL.join(parts)


# ------------------------------------------------------------
# 受付ページ
# ------------------------------------------------------------
def mail_body():
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
        return send, '<span style="color:var(--shu);font-weight:600">要記入</span>', True

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


# ------------------------------------------------------------
def put_link(doc, url, url_marker, state_marker):
    """決済リンク。未設定なら押せない見た目にする（リンク切れを出さない）。"""
    if url:
        return doc.replace(url_marker, url).replace(state_marker, ""), False
    doc = doc.replace('href="%s"' % url_marker, 'href="#" aria-disabled="true"')
    return doc.replace(state_marker, " is-pending"), True


def main():
    ap = argparse.ArgumentParser(description="販売ページを1枚のHTMLに組み立てる")
    ap.add_argument("--template", default=os.path.join(SITE, "index.template.html"))
    ap.add_argument("--out", default=os.path.join(SITE, "index.html"))
    ap.add_argument("--buy-url", default=None,
                    help="お試し(19,800円)の決済リンク。未指定なら購入ボタンは準備中の見た目になる")
    ap.add_argument("--buy-url-single", default=None,
                    help="単発(49,800円)の決済リンク")
    ap.add_argument("--contact-email", default=None,
                    help="お客さんからの連絡を受けるメールアドレス")
    args = ap.parse_args()

    with open(args.template, encoding="utf-8") as f:
        html = f.read()

    # ---- サンプルのコマを焼き込む ----
    tmp = tempfile.mkdtemp(prefix="patti_site_")
    total = 0
    n_img = 0
    for spec in SAMPLES:
        video = latest_render(spec["dir"])
        print("素材: %s" % os.path.relpath(video, BASE))
        for i, sec in enumerate(spec["marks"], 1):
            jpg = os.path.join(tmp, "%s_%d.jpg" % (spec["key"], i))
            grab(video, sec, jpg)
            with open(jpg, "rb") as f:
                raw = f.read()
            total += len(raw)
            n_img += 1
            uri = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
            marker = "__%sF%d__" % (spec["key"], i)
            if marker not in html:
                raise SystemExit("テンプレートに %s がありません" % marker)
            html = html.replace(marker, uri)
            print("  %s  t=%ss  %.1f KB" % (marker, sec, len(raw) / 1024))

    # ---- 決済リンク ----
    html, p1 = put_link(html, args.buy_url, "__BUY_URL__", "__BUY_STATE__")
    html, p2 = put_link(html, args.buy_url_single, "__BUY_URL2__", "__BUY2_STATE__")
    pending_buy = p1 or p2

    # ---- 構造化データ（本文のFAQから組む）----
    jsonld, n_offer, n_faq = build_jsonld(
        html, args.buy_url, args.buy_url_single, args.contact_email)
    if "__JSONLD__" not in html:
        raise SystemExit("テンプレートに __JSONLD__ がありません")
    html = html.replace("__JSONLD__", jsonld)
    print("構造化データ: Organization / Service(Offer %d件) / FAQPage(%d問)" % (n_offer, n_faq))

    # ---- 完全なHTMLとして書き出す ----
    head, body = split_head(html)
    if head is None:
        raise SystemExit("テンプレートに <!--HEAD--> がありません")
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        f.write(wrap_document(head, body))

    # Artifact公開用の断片（doctype/html/head/body を含めない形）
    frag = os.path.join(SITE, "preview.html")
    with open(frag, "w", encoding="utf-8", newline="") as f:
        f.write(head + NL + body + NL)

    # ---- 相場ページ ----
    # 購入意図がいちばん濃い検索語（「ショート動画 外注 相場」）に正面から答える。
    pz_tpl = os.path.join(SITE, "price.template.html")
    pz_out = os.path.join(SITE, "price.html")
    if os.path.isfile(pz_tpl):
        with open(pz_tpl, encoding="utf-8") as f:
            pz = f.read()
        pz_ld, pz_faq = build_price_jsonld(pz)
        pz = pz.replace("__JSONLD__", pz_ld)
        pz, _ = put_link(pz, args.buy_url, "__BUY_URL__", "__BUY_STATE__")
        pz_head, pz_body = split_head(pz)
        with open(pz_out, "w", encoding="utf-8", newline="") as f:
            f.write(wrap_document(pz_head, pz_body) if pz_head is not None else pz)
        print("出力: %s  %.0f KB（FAQ %d問）"
              % (os.path.relpath(pz_out, BASE), os.path.getsize(pz_out) / 1024, pz_faq))

    # ---- 工程ページ ----
    # 「打ち合わせなしで本当に作れるのか」が一番の不安なので、工程を全部見せる。
    pr_tpl = os.path.join(SITE, "process.template.html")
    pr_out = os.path.join(SITE, "process.html")
    if os.path.isfile(pr_tpl):
        with open(pr_tpl, encoding="utf-8") as f:
            pr = f.read()
        pr = pr.replace("__JSONLD__", build_process_jsonld())
        pr, _ = put_link(pr, args.buy_url, "__BUY_URL__", "__BUY_STATE__")
        pr_head, pr_body = split_head(pr)
        with open(pr_out, "w", encoding="utf-8", newline="") as f:
            f.write(wrap_document(pr_head, pr_body) if pr_head is not None else pr)
        print("出力: %s  %.0f KB" % (os.path.relpath(pr_out, BASE),
                                     os.path.getsize(pr_out) / 1024))

    # ---- 受付ページ ----
    pending_mail = False
    t_tpl = os.path.join(SITE, "thanks.template.html")
    t_out = os.path.join(SITE, "thanks.html")
    if os.path.isfile(t_tpl):
        with open(t_tpl, encoding="utf-8") as f:
            th = f.read()
        send, contact, pending_mail = build_send_block(args.contact_email)
        th = th.replace("__SEND_BLOCK__", send).replace("__CONTACT_PLAIN__", contact)
        t_head, t_body = split_head(th)
        out_html = wrap_document(t_head, t_body) if t_head is not None else th
        with open(t_out, "w", encoding="utf-8", newline="") as f:
            f.write(out_html)
        print("出力: %s  %.0f KB%s" % (
            os.path.relpath(t_out, BASE), os.path.getsize(t_out) / 1024,
            "  ← 連絡先メール未設定" if pending_mail else ""))

    print("出力: %s  %.0f KB" % (os.path.relpath(args.out, BASE),
                                 os.path.getsize(args.out) / 1024))
    print("出力: %s  %.0f KB（Artifact公開用）"
          % (os.path.relpath(frag, BASE), os.path.getsize(frag) / 1024))
    print("画像: %d 枚 / 元 %.0f KB" % (n_img, total / 1024))

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
