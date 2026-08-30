# 縦動画を3営業日で ─ STUDIO PATTI

縦型ショート動画（1080×1920）の制作を、**固定価格・打ち合わせなし・3営業日**で承っています。

**販売ページ** → https://ikemotodir.github.io/patti-reel/

| プラン | 価格（税込） | 尺 | 納期 | 修正 |
|---|---|---|---|---|
| お試し（1社1回限り） | ¥19,800 | 30秒まで | 3営業日 | 1回 |
| 単発 | ¥49,800 | 60秒まで | 3営業日 | 1回 |
| 定額 月4本 | ¥148,000/月 | 各60秒まで | 各3営業日 | 各1回 |

決済は Stripe。カード情報が当方に渡ることはありません。

---

## このリポジトリの中身

| ファイル | 中身 |
|---|---|
| `index.html` | 販売ページ（生成物） |
| `thanks.html` | 決済後の受付ページ（生成物） |
| `index.template.html` | 販売ページの原本 |
| `thanks.template.html` | 受付ページの原本 |
| `build.py` | 原本 → 生成物 の組み立て |
| `stripe_product_image.jpg` | Stripe商品ページ用の画像 |

**`index.html` と `thanks.html` は生成物です。直接編集しないでください。**
原本（`*.template.html`）を直して、組み立て直します。

```bash
python build.py \
  --buy-url "https://buy.stripe.com/..." \
  --buy-url-single "https://buy.stripe.com/..." \
  --contact-email "..."
```

サンプル動画の代表コマは、最新のレンダー（`../works/*/renders/*.mp4`）から自動で抜いて
data URI として焼き込まれます。**画像が外部ファイルにならないので、どこに置いてもリンクが切れません。**

動画そのものの作り方は `../README.md` を見てください。

---

© 2026 STUDIO PATTI LLC
