# Windows startup

このメモは、開発環境のまま `start_selfcontrol_app.bat` でアプリを起動するための手順です。

## 初回セットアップ

リポジトリ直下で以下を実行します。

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

## ダブルクリックで起動する

1. `start_selfcontrol_app.bat` をダブルクリックします。
2. Selfcontrol Planner のウィンドウが開くことを確認します。
3. エラーが出た場合は、コマンドプロンプトが閉じずに止まるので、表示された内容を確認します。

`start_selfcontrol_app.bat` は、ダブルクリックした場所ではなく、batファイル自身の場所を基準に `app.py` を起動します。

## Windows起動時に開く

1. `Win + R` を押します。
2. `shell:startup` と入力して Enter を押します。
3. 開いたスタートアップフォルダに、`start_selfcontrol_app.bat` のショートカットを置きます。
4. 次回Windows起動時に、ショートカット経由でアプリが起動します。

ショートカットは、`start_selfcontrol_app.bat` を右クリックして「ショートカットの作成」を選ぶと作れます。

## 注意

- OS通知はまだ未対応です。
- トレイ常駐はまだ未対応です。
- exe化はまだ未対応です。
- Windows自動起動そのものは、スタートアップフォルダにショートカットを置く簡易運用です。
