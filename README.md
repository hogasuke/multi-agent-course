# マルチエージェントコース

Claude Codeのマルチエージェント機能を学習する実習プロジェクト。

---

## プロジェクト概要

本プロジェクトは、Claude Codeが提供するマルチエージェント機能（コードレビュー、テスト生成、ドキュメント作成など）を実際に体験しながら学習するためのサンプルアプリケーションです。

メインの実装として、JSONファイルを永続化ストレージとして使用するTodoリスト管理クラス（`TodoList`）を含んでいます。

---

## 技術スタック

| 項目 | 内容 |
|------|------|
| 言語 | Python 3.14.2 |
| パッケージ管理 | [uv](https://docs.astral.sh/uv/) |
| テストフレームワーク | pytest |
| Webフレームワーク | FastAPI |

---

## セットアップ方法

### 前提条件

- Python 3.14.2 以上
- uv がインストール済みであること

uvのインストールは[公式ドキュメント](https://docs.astral.sh/uv/getting-started/installation/)を参照してください。

### 手順

```bash
# リポジトリをクローン
git clone <リポジトリURL>
cd multi-agent-course

# 依存パッケージをインストール
uv sync
```

> **注意:** `pip install` は使用しないこと。パッケージの追加は必ず `uv add <パッケージ名>` を使う。

---

## 使い方

### TodoListクラスの基本的な使用例

```python
from src.todo import TodoList

# インスタンス生成（JSONファイルが事前に存在している必要がある）
tl = TodoList("todos.json")

# タスクを追加する
todo = tl.add("牛乳を買う")
print(todo)
# {'id': 1, 'title': '牛乳を買う', 'done': False}

# 全タスクを一覧取得する
all_todos = tl.list_all()

# タスクを完了にする
tl.complete(todo["id"])

# タスクを検索する（大文字小文字を区別する）
results = tl.search("買う")

# タスクを削除する
tl.delete(todo["id"])

# 統計情報を取得する（タスクが1件以上存在する場合のみ）
stats = tl.get_stats()
print(stats)
# {'total': 1, 'done': 1, 'pending': 0, 'rate': 1.0}
```

スクリプトの実行には `uv run python` を使う。

```bash
uv run python main.py
```

---

## テスト実行方法

```bash
uv run pytest
```

詳細な出力を確認したい場合は `-v` オプションを付ける。

```bash
uv run pytest -v
```

### テスト結果

| 項目 | 内容 |
|------|------|
| テストファイル | `tests/test_todo.py` |
| テスト件数 | 29件（全件パス） |
| カバー内容 | 正常系・異常系・エッジケース・境界値テスト |

#### テストクラス一覧

| クラス名 | 対象メソッド | テスト件数 |
|----------|-------------|------------|
| `TestAdd` | `add()` | 4件 |
| `TestListAll` | `list_all()` | 2件 |
| `TestComplete` | `complete()` | 2件 |
| `TestDelete` | `delete()` | 2件 |
| `TestSearch` | `search()` | 2件 |
| `TestGetStats` | `get_stats()` | 2件 |
| `TestEdgeCases` | 各メソッドの異常系 | 9件 |
| `TestBoundary` | 境界値 | 6件 |

---

## ディレクトリ構成

```
multi-agent-course/
├── src/              # メインのソースコード
│   └── todo.py       # TodoListクラスの実装
├── tests/            # テストコード
│   └── test_todo.py  # TodoListのテスト（29件）
├── docs/             # ドキュメント
├── main.py           # エントリーポイント
├── pyproject.toml    # プロジェクト設定・依存関係
├── uv.lock           # uvのロックファイル
└── README.md         # 本ファイル
```

---

## 既知の問題

コードレビューによって以下の問題が確認されている。今後の修正対象として記録する。

### 高優先度

| 問題箇所 | 内容 |
|----------|------|
| `load()` | ファイルが存在しない場合に `FileNotFoundError` が発生する。例外処理が実装されておらず、初回起動時にクラッシュする |
| `get_stats()` | タスクが0件のとき `done / total` の計算で `ZeroDivisionError` が発生する |
| `load()` / `save()` | `with` 文を使用していないため、例外発生時にファイルディスクリプタがリークする可能性がある |
| `complete()` | 存在しないIDを指定した場合、例外を送出せず暗黙的に `None` を返す |
| `delete()` | 存在しないIDを指定した場合、例外を送出せず暗黙的に `None` を返す |
| `filepath` | パストラバーサル（`"../../etc/passwd"` など）に対する入力検証がない |
| `add()` | タイトルの入力値検証（空文字チェック・長さ制限など）がない |

### 中優先度

| 問題箇所 | 内容 |
|----------|------|
| `search()` | 大文字小文字を区別するため、`"buy"` で `"Buy"` はヒットしない |
| `load()` / `save()` | `open()` に `encoding` を指定していないため、実行環境によっては日本語が文字化けするリスクがある |
| 全メソッド | 型アノテーションが付与されていない |

---

## 開発ルール

- コメントとドキュメントは日本語で記述する
- パッケージの追加は `uv add` を使う（`pip install` は使用禁止）
- スクリプト実行は `uv run python` を使う
- テスト実行は `uv run pytest` を使う
