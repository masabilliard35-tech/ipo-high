# 上場来高値 スクリーナー（新規上場銘柄）

東証の全銘柄から、**上場5か月〜3年 × 最初の2か月を除外した上場来高値を更新中** の銘柄を
自動で毎日スクリーニングし、Webアプリで表示・当日更新をチャット通知する仕組み。
業績（利益率・ROE等）は条件に含めない。株価だけで判定するためレート制限に強い。

## 条件

1. 上場から5か月〜3年
2. 上場後の最初の2か月を除外した「上場来高値」を更新中（当日が高値圏）
3. 毎日、当日に上場来高値を更新した銘柄を検知して通知

## 構成

| ファイル | 役割 |
|---|---|
| `scan.py` | データ取得・絞り込みの本体 |
| `app.py` | Streamlitの画面（表・チャート） |
| `notify.py` | 通知の送信（Discord / LINE） |
| `universe.py` | 対象銘柄リストの取得 |
| `.github/workflows/daily.yml` | 毎日17:30 JSTに株価更新＋通知 |
| `data/` | 生成データ（自動コミットされる） |

## 仕組み

```
毎日17:30 daily.yml → scan.py → data/rows.json ＋ 当日の上場来高値更新を通知
利用者     app.py（Streamlit Cloud） → data/rows.json を表示、チャートはライブ取得
```

## セットアップ手順

### 1. GitHubにリポジトリを作る
1. GitHubで新規リポジトリ `ipo-high` を作成（公開推奨＝Actions無制限）
2. このフォルダの中身をすべて push

```bash
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/<あなた>/ipo-high.git
git push -u origin main
```

### 2. 通知先を用意する（Discord推奨）
1. Discordでチャンネルの Webhook URL を作成
2. GitHubリポジトリの Settings → Secrets and variables → Actions → New repository secret
   - 名前 `DISCORD_WEBHOOK`、値にコピーしたURL

（LINEを使う場合は `LINE_TOKEN` と `LINE_USER_ID` を登録。旧LINE Notifyは2025年3月終了）

### 3. 初回データを作る
GitHubの Actions タブ →「daily-scan」→ Run workflow（手動実行）で `data/rows.json` ができる。

### 4. Streamlit Cloudにデプロイ
1. [share.streamlit.io](https://share.streamlit.io/) にGitHubでログイン
2. New app → リポジトリ `ipo-high`、ブランチ `main`、ファイル `app.py` を選択 → Deploy

以降、毎日17:30に自動更新＋通知され、アプリを開けば常に最新が見られる。

## ローカルで試す
```bash
pip install -r requirements.txt
python scan.py
streamlit run app.py
```

## 注意
- 上場日は株価履歴の最初の営業日で近似（新規上場銘柄では実態とほぼ一致）。
- 上場来高値は上場後2か月を除外して算出。
- スクリーニング補助であり投資助言ではない。
