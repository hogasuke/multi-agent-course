# multi-agent-course

Claude Code のマルチエージェント機能を学習する実習プロジェクト。
コアモジュールとして、JSONファイルを永続化ストレージとするTodo管理クラス `TodoList` を実装している。

## プロジェクト概要

`src/todo.py` に実装された `TodoList` クラスは、以下の特徴を持つ。

- 追加・完了・削除などの操作を行うたびに自動的にJSONファイルへ書き込む
- プロセスを再起動してもデータが失われない永続化設計
- ファイルが存在しない場合や破損している場合は空の状態で安全に起動する
- 日本語タイトルを含むデータを正しく保存・読み込みできる

## 機能一覧

| メソッド | 説明 |
|---|---|
| `add(title)` | 新しいTodoを追加する。タイトルの前後空白は自動除去。 |
| `list_all()` | 全Todoのリストを返す（内部データのコピー）。 |
| `complete(todo_id)` | 指定IDのTodoを完了状態にする。 |
| `delete(todo_id)` | 指定IDのTodoを削除する。 |
| `search(keyword)` | キーワードで部分一致検索する（大文字小文字を区別しない）。 |
| `get_stats()` | 総数・完了数・未完了数・完了率の統計情報を返す。 |

## セットアップ

Python 3.14 以上および [uv](https://docs.astral.sh/uv/) が必要。

```bash
# リポジトリのクローン
git clone <リポジトリURL>
cd multi-agent-course

# 依存関係のインストール
uv sync
```

## 使い方

### 基本的な使用例

```python
from src.todo import TodoList

# インスタンス化（指定ファイルが存在すれば自動的に読み込む）
todo_list = TodoList("todos.json")

# Todoを追加する
item = todo_list.add("牛乳を買う")
print(item)
# {'id': 1, 'title': '牛乳を買う', 'done': False}

todo_list.add("Python学習")
todo_list.add("レポートを提出する")
```

### 一覧取得

```python
# 全件取得
all_todos = todo_list.list_all()
for todo in all_todos:
    status = "完了" if todo["done"] else "未完了"
    print(f"[{status}] {todo['id']}: {todo['title']}")
```

### 完了・削除

```python
# IDを指定して完了状態にする
result = todo_list.complete(1)
print(result)
# {'id': 1, 'title': '牛乳を買う', 'done': True}

# 存在しないIDを指定するとNoneが返る
print(todo_list.complete(999))
# None

# IDを指定して削除する（成功時はTrue、失敗時はFalse）
print(todo_list.delete(2))
# True
```

### 検索

```python
# 大文字小文字を区別せず部分一致で検索する
results = todo_list.search("python")
for todo in results:
    print(todo["title"])
# Python学習

# 空文字を指定すると全件が返る
all_results = todo_list.search("")
```

### 統計情報

```python
stats = todo_list.get_stats()
print(stats)
# {'total': 2, 'done': 1, 'pending': 1, 'rate': 0.5}
print(f"完了率: {stats['rate'] * 100:.1f}%")
# 完了率: 50.0%
```

## テスト実行

```bash
uv run pytest
```

詳細なログを確認したい場合は `-v` オプションを付ける。

```bash
uv run pytest -v
```

現在のテストスイートは37件のテストケースから構成される。

| テストクラス | 件数 | 検証内容 |
|---|---|---|
| TestLoad | 4件 | ファイル未存在・破損JSON・キー欠落・正常読み込み |
| TestAdd | 8件 | 連番ID・空白trim・done初期値、異常系バリデーション |
| TestListAll | 5件 | 空リスト・複数件・コピー確認・内部変更不可 |
| TestComplete | 5件 | フラグ更新・再完了・存在しないID・負のID |
| TestDelete | 5件 | 削除後の非存在・他データ残存・存在しないID |
| TestSearch | 5件 | 部分一致・大文字小文字無視・空キーワード全件 |
| TestGetStats | 5件 | rate計算・0件時のZeroDivisionError防止 |

## データ形式

TodoリストはJSONファイルに以下の形式で保存される。

```json
{
  "todos": [
    {"id": 1, "title": "牛乳を買う", "done": true},
    {"id": 2, "title": "Python学習", "done": false},
    {"id": 3, "title": "レポートを提出する", "done": false}
  ],
  "next_id": 4
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `todos` | array | Todoオブジェクトの配列 |
| `todos[].id` | integer | Todo固有のID（削除されても再利用しない連番） |
| `todos[].title` | string | Todoのタイトル（最大200文字） |
| `todos[].done` | boolean | 完了フラグ（初期値はfalse） |
| `next_id` | integer | 次に付与するID |

## エラーハンドリング

`add()` メソッドは以下の例外を発生させる。

| 例外 | 発生条件 | 例 |
|---|---|---|
| `TypeError` | `title` が `str` 型でない場合 | `add(None)`, `add(123)` |
| `ValueError` | `title` が空文字または空白のみの場合 | `add("")`, `add("   ")` |
| `ValueError` | `title` が201文字以上の場合 | `add("あ" * 201)` |

```python
from src.todo import TodoList

todo_list = TodoList()

try:
    todo_list.add(None)
except TypeError as e:
    print(f"TypeError: {e}")
# TypeError: titleはstr型でなければなりません

try:
    todo_list.add("")
except ValueError as e:
    print(f"ValueError: {e}")
# ValueError: titleは空文字にできません

try:
    todo_list.add("あ" * 201)
except ValueError as e:
    print(f"ValueError: {e}")
# ValueError: titleは200文字以内でなければなりません
```

## ディレクトリ構成

```
multi-agent-course/
├── src/
│   └── todo.py          # TodoListクラスの実装
├── tests/
│   └── test_todo.py     # pytestによるテストコード
├── docs/                # 追加ドキュメント用ディレクトリ
├── main.py              # エントリーポイント
├── pyproject.toml       # プロジェクト設定・依存関係
├── CLAUDE.md            # Claude Code向けプロジェクト指示
└── README.md            # このファイル
```

## 技術スタック

- Python 3.14.2
- パッケージ管理: uv
- テスト: pytest
- フレームワーク: FastAPI（将来的な拡張用）
