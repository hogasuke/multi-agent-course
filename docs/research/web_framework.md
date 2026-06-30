現状を把握しました。プロジェクトの依存関係（uv管理、CLAUDE.mdの開発ルール）とTodoListクラスの実装を踏まえてレポートを作成します。

---

# Webフレームワーク比較調査レポート：Todoアプリの本格Web化に向けて

## 前提：現状のプロジェクト

- `src/todo.py` の `TodoList` クラスは、JSONファイル永続化によるシンプルな同期処理（add / list_all / complete / delete / search / get_stats）
- 依存関係は `httpx`、`requests`、開発用に `pytest` のみ。Webフレームワークは未導入
- パッケージ管理は `uv`、Python 3.14系を使用
- 永続化層がJSONファイルであり、本格運用にはDB移行（SQLite/PostgreSQL + ORM）も視野に入る規模感

## 比較表

| 観点 | FastAPI | Flask | Django |
|---|---|---|---|
| 学習コスト | 中（型ヒント・Pydanticの理解が前提） | 低（最小限のAPIで直感的） | 高（フルスタックの規約・機能が多い） |
| 非同期サポート | ◎ ネイティブ対応（async/await標準） | △ 標準は同期、Flask 2.0+で部分対応 | ○ Django 4.1+でASGI/async view対応が進行中 |
| エコシステム | 成長中。Pydantic/SQLModel/SQLAlchemyと好相性。軽量で自由度が高い | 非常に成熟。拡張機能（Flask-SQLAlchemy等）が豊富 | 最も成熟。ORM・管理画面・認証が標準搭載、巨大なエコシステム |
| パフォーマンス | ◎ ASGI（Starlette基盤）で高速、I/Oバウンドに強い | ○ WSGIベースで標準的、非同期は弱め | ○ WSGI標準、ASGI対応は発展途上で重量級 |
| 型安全性・自動ドキュメント | ◎ Pydanticによる型検証 + Swagger UI/ReDoc自動生成 | × 標準では型検証・APIドキュメント自動生成なし | △ DRF併用で可能だが追加導入が必要 |

## 各観点の解説

### 学習コスト
Flaskが最も低く、最小構成なら数行でAPIを書ける。FastAPIは型ヒントとPydanticモデルの理解が必要だが、現代的なPython（型ヒント前提）に慣れていれば習得は速い。Djangoはプロジェクト構成・ORM・管理画面・URLルーティングなど学ぶべき範囲が広く、フルスタック開発の規約を受け入れる必要がある。

### 非同期サポート
FastAPIはASGI（Starlette）をベースに設計段階から非同期を前提としており、`async def` でエンドポイントを書くのが自然。現在の `TodoList` は同期的なファイルI/Oだが、将来DBアクセスやネットワークI/Oが増えると非同期処理の恩恵が大きい。FlaskはWSGIベースで非同期は後付け（Flask 2.0以降一部対応）。DjangoもASGI対応は進んでいるが、Django ORM自体は伝統的に同期前提で、非同期化は部分的。

### エコシステム
DjangoはORM・認証・管理画面（Django Admin）・フォーム処理が標準搭載で、「バッテリー同梱」の思想。大規模・長期運用のサービスに向く。FlaskはシンプルなコアにFlask-SQLAlchemy、Flask-Loginなど拡張機能を組み合わせるスタイルで自由度が高い。FastAPIはPydantic（データバリデーション）、SQLModel/SQLAlchemy（ORM）との組み合わせが定番で、エコシステムはDjangoほど広くないが、現在のTodoアプリ規模には十分。

### パフォーマンス
FastAPIはASGI + Pydanticの効率的なバリデーションにより、特にI/Oバウンドな処理（DBアクセス、外部API呼び出し）で高いスループットを発揮する。本プロジェクトはすでに `httpx` を依存に持っており、外部APIとの非同期連携を見据えている可能性がある点も合致する。FlaskとDjangoは同期WSGIが基本で、高並列が必要な場面ではFastAPIに劣る。

## 推奨フレームワーク：**FastAPI**

### 理由
1. **既存コードとの親和性**：`TodoList` のメソッドはほぼそのままサービス層として再利用可能。FastAPIのPydanticモデルでリクエスト/レスポンスのバリデーション（titleの空文字・200文字制限など、現在`add()`内で行っている検証）を宣言的に書き直せる。
2. **小〜中規模アプリに最適**：Todoアプリ程度の規模ではDjangoの機能（管理画面・認証フレームワークなど）は過剰。FastAPIは必要な機能を必要なだけ追加できる。
3. **自動APIドキュメント**：Swagger UI / ReDocが自動生成され、フロントエンド連携や学習目的のコース教材としても説明しやすい。
4. **既存依存との一貫性**：`httpx` がすでに依存に含まれており、非同期エコシステムとの相性が良い。
5. **型ヒント前提の設計**：CLAUDE.mdのルールに「日本語コメント・docstring」とあるように、型ヒントとdocstringを重視する現在のコードスタイル（`todo.py` 参照）とFastAPIの設計思想が一致する。

Django・Flaskを推さない理由は、Djangoは学習コストとプロジェクトの重さが現状の規模に見合わず、Flaskは型安全性・非同期対応・自動ドキュメントの面でFastAPIに劣るため。

## 導入ロードマップ（次の一歩）

1. **依存追加**：`uv add fastapi uvicorn[standard]` でFastAPI本体とASGIサーバーを追加
2. **APIスキーマ定義**：`TodoList.add()` 等のバリデーションロジックをPydanticモデル（`TodoCreate`、`TodoResponse`等）に移植
3. **ルーター層の作成**：`src/api/` 等を新設し、既存の `TodoList` をサービス層として呼び出すエンドポイント（`POST /todos`、`GET /todos`、`PATCH /todos/{id}/complete`、`DELETE /todos/{id}` など）を実装
4. **テスト整備**：`uv add --dev httpx` は既に依存にあるためFastAPIの `TestClient` をそのまま活用し、`uv run pytest` でAPIテストを追加
5. **永続化層の検討**：将来的にJSONファイルからSQLite（SQLModelやSQLAlchemy）への移行を検討し、`TodoList` のインターフェースを維持したまま内部実装を差し替える
6. **起動確認**：`uv run uvicorn src.main:app --reload` で動作確認
