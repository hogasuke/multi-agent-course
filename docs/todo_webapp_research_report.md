# Todoアプリ Web化 統合調査レポート

エージェントチーム（tmuxの3ペインで並列実行）による調査結果の統合レポート。

- チームメイト1: Webフレームワーク調査 → [詳細](research/web_framework.md)
- チームメイト2: データベース設計 → [詳細](research/database_design.md)
- チームメイト3: デプロイ戦略 → [詳細](research/deploy_strategy.md)

## 1. エグゼクティブサマリー

| 観点 | 推奨 | 理由（要約） |
|---|---|---|
| Webフレームワーク | **FastAPI** | 既存`TodoList`の`dict`構造とPydanticの親和性が高い。非同期ネイティブ、OpenAPI自動生成、`pytest`との相性も良い |
| データベース（開発） | **SQLite** | セットアップ不要、`pytest`との相性が良くCIにも追加インフラ不要 |
| データベース（本番） | **PostgreSQL** | FastAPIを複数ワーカーで動かす前提では同時書き込み耐性が必要 |
| コンテナ化 | **Docker（マルチステージ、uvベース）** | ビルドキャッシュを活かしつつ本番イメージを最小化できる |
| デプロイ先 | **Render** | 学習用途に十分な無料枠、Dockerfileベースの容易なデプロイ、GitHub Actions連携が容易 |

3つの調査は独立して進めたが、推奨同士に矛盾はなく、**FastAPI + SQLAlchemy/SQLModel + Alembic + Docker + Render** という一貫した技術スタックに収束した。

## 2. 現状（共通認識）

3チームメイトとも `src/todo.py` を読み、以下を前提として調査した。

- `TodoList`クラスがCRUD・検索・統計をJSONファイル（同期I/O、トランザクション性なし）で実装
- `id`/`title`/`done`のみを持つシンプルなデータモデル
- 依存関係は`httpx`/`requests`/`pytest`のみで、Web層・ORM・非同期処理は未導入
- `uv`によるパッケージ管理、Python 3.14

この現状認識が3つの調査結果で一致しており、後述の統合ロードマップの土台になっている。

## 3. 技術選定の整合性

- **FastAPI × データベース**：FastAPIの作者によるSQLModel（SQLAlchemy + Pydantic統合）を使えば、APIスキーマとDBスキーマを同じモデル定義で扱える。データベース調査が提案する開発(SQLite)/本番(PostgreSQL)の使い分けも、SQLAlchemy経由であれば方言差を吸収しやすい。
- **FastAPI × デプロイ**：デプロイ調査のサンプルDockerfileは`fastapi run`コマンドを起動コマンドとしており、フレームワーク調査の推奨と直接整合している。
- **データベース × デプロイ**：Renderの無料PostgreSQLは30日で自動削除される制約があるため、本番DBを使い始める段階でこの制約を踏まえた切替え（有料DB or 外部マネージドDB）を検討する必要がある。

## 4. リスク・注意点（統合）

1. **Render無料PostgreSQLの30日削除制約**：永続データが必要になった時点で有料化または外部DB（Neon、Supabase等）への切替えが必須。
2. **SQLite/PostgreSQLの方言差**：開発・本番で異なるDBを使う場合、ORM（SQLAlchemy/SQLModel）を必ず経由し、CIでもPostgreSQLに対するテストを定期実行することでギャップを埋める。
3. **無料Web Serviceのコールドスタート**：Renderの無料枠は15分非アクセスでスピンダウンし、デモ時に30〜60秒の遅延が起きうる。発表直前は有料プランへの一時切替えも検討。

## 5. 統合ロードマップ

1. **Webアプリ化の土台作り**
   - `uv add fastapi "uvicorn[standard]"`
   - `TodoList`の`dict`構造に対応するPydanticモデル（`TodoCreate`/`TodoResponse`）を定義
   - `src/api.py`にAPIRouterを作成し、既存`TodoList`を薄くラップするエンドポイントを実装（`POST /todos`、`GET /todos`、`PATCH /todos/{id}/complete`、`DELETE /todos/{id}`、`GET /todos/search`、`GET /todos/stats`）
   - `TestClient`を使ったエンドポイントテストを`tests/`に追加（`uv run pytest`で実行）

2. **データ永続化の段階移行**
   - SQLAlchemy/SQLModelで`Todo`モデルを定義し、Alembicでスキーマ管理を開始（開発環境はSQLite）
   - `TodoList`のインターフェースを維持したまま内部実装をDBアクセスに置き換え、既存テストへの影響を最小化
   - 既存`todos.json`を1回限りの移行スクリプトでDBに取り込む

3. **コンテナ化とデプロイ**
   - マルチステージDockerfile（uvベース）と`.dockerignore`を追加し、ローカルで`docker build`/`docker run`を確認
   - GitHubリポジトリと連携し、RenderでDockerfileベースのWeb Serviceを作成
   - GitHub Actionsで`uv run pytest`を実行し、テスト通過後にRenderへ自動デプロイされるCI/CDを整備

4. **本番DBへの移行**
   - 永続データが必要になった段階でRender無料Postgres（30日制約あり）から有料DBまたは外部マネージドPostgreSQLへ切替え
   - Alembicマイグレーションを本番環境に適用

## 6. 各レポートへのリンク

詳細な比較表・解説・サンプルコードは個別レポートを参照。

- [Webフレームワーク調査（FastAPI/Flask/Django比較）](research/web_framework.md)
- [データベース設計（SQLite/PostgreSQL比較・推奨スキーマ）](research/database_design.md)
- [デプロイ戦略（Docker化・PaaS比較）](research/deploy_strategy.md)
