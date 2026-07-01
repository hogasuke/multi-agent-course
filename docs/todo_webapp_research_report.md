# Todoアプリ Web化 統合調査レポート

エージェントチーム（tmuxの3ペインで並列実行）による調査結果の統合レポート。

- チームメイト1: Webフレームワーク調査 → [詳細](research/web_framework.md)
- チームメイト2: データベース設計 → [詳細](research/database_design.md)
- チームメイト3: デプロイ戦略 → [詳細](research/deploy_strategy.md)

## 1. エグゼクティブサマリー

| 観点 | 推奨 | 理由（要約） |
|---|---|---|
| Webフレームワーク | **FastAPI** | 既存`TodoList`のCRUD＋検索＋統計という構造・型ヒントの徹底がPydanticと直接噛み合う。ASGIネイティブで非同期化も素直、CLAUDE.mdの技術スタックにも既に明記済み |
| データベース（開発） | **SQLite** | セットアップ不要、`uv run`だけで動き`pytest`との相性も良い |
| データベース（本番） | **PostgreSQL** | 複数ワーカー・将来のユーザー管理を見据えた同時書き込み耐性とMVCCが必要 |
| コンテナ化 | **Docker（マルチステージ、uvベース）** | `--no-install-project`でレイヤーキャッシュを効かせつつ、非rootユーザー・ヘルスチェック込みで本番イメージを最小化 |
| デプロイ先 | **Render（Starterプラン〜）+ GitHub連携自動デプロイ** | 学習用途は無料枠で足り、常時稼働ならStarter（$7/月〜）。Dockerfileベースで難易度が低くIaC（render.yaml）も可能 |

3つの調査は独立して進めたが、推奨同士に矛盾はなく、**FastAPI + SQLAlchemy(async)/Alembic + Docker + Render** という一貫した技術スタックに収束した。

## 2. 現状（共通認識）

3チームメイトとも `src/todo.py` と `CLAUDE.md` を読み、以下を前提として調査した。

- `TodoList`クラスが`id`/`title`/`done`のCRUD・検索・統計をJSONファイル（同期I/O、トランザクション性なし）で実装
- 型ヒントと日本語docstringを徹底しており、外部依存はほぼゼロ
- 依存関係は`httpx`/`requests`/`pytest`のみで、Web層・ORM・非同期処理・DB・コンテナは未導入
- `uv`によるパッケージ管理、Python 3.14、`pip install`禁止

この現状認識が3つの調査結果で一致しており、後述の統合ロードマップの土台になっている。

## 3. 技術選定の整合性

- **FastAPI × データベース**：`TodoList`のCRUD操作（`add`/`list_all`/`complete`/`delete`/`search`/`get_stats`）はSQLAlchemyモデル＋FastAPIエンドポイントに1対1で対応させやすく、DB調査が提案するSQLite（開発）/PostgreSQL（本番）の使い分けも、SQLAlchemy経由であれば方言差（`AUTOINCREMENT`、外部キー制約のデフォルト無効など）を吸収できる。
- **FastAPI × デプロイ**：デプロイ調査のDockerfileは`uvicorn src.main:app`を起動コマンドとしており、フレームワーク調査の推奨と直接整合している。
- **データベース × デプロイ**：現状のJSONファイル永続化のままRenderへデプロイすると、再デプロイ時にファイルシステムがリセットされ**データが消える**。DB調査の結論（SQLite→PostgreSQL移行）とデプロイ調査の指摘が一致しており、Web化と同時にDB移行が事実上必須という共通の警告になっている。

## 4. リスク・注意点（統合）

1. **JSON永続化のままのデプロイは危険**：Render/Railwayはコンテナのローカルファイルシステムが再デプロイ・スケール時にリセットされるため、`todos.json`は消失する。FastAPI化と同時にDB移行（SQLite→PostgreSQL）を行うこと。
2. **Render無料PostgreSQLの30日失効制約**（猶予14日）：永続データが必要になった時点で有料DBまたは外部マネージドDB（Neon、Supabase等）への切替えを検討する。
3. **SQLite/PostgreSQLの方言差**：外部キー制約のデフォルト無効化、`ALTER TABLE`の制約変更の制限（Alembicの`render_as_batch=True`で対応）など、開発・本番で挙動が変わりうる点はORM経由で吸収し、CIでもPostgreSQLに対するテストを定期実行してギャップを埋める。
4. **無料Web Serviceのコールドスタート**：Renderの無料枠は15分無操作でスピンダウンし、次リクエストで約1分の遅延が起きる。デモ・発表前は有料プランへの一時切替えも検討。
5. **従量課金の見積もりにくさ**：Railwayは完全従量課金のため、動かしっぱなしで気づかないうちにコストが増える可能性がある。学習用途ではコストを固定しやすいRenderの方が扱いやすい。

## 5. 統合ロードマップ

1. **Webアプリ化の土台作り**
   - `uv add fastapi "uvicorn[standard]"`
   - `TodoList`の構造に対応するPydanticモデル（`TodoCreate`/`TodoResponse`）を定義
   - `src/main.py`（または`api.py`）にAPIRouterを作成し、既存`TodoList`を依存性注入（`Depends`）で薄くラップするエンドポイントを実装（`POST /todos`、`GET /todos`、`PATCH /todos/{id}/complete`、`DELETE /todos/{id}`、`GET /todos/search`、`GET /todos/stats`）
   - `add`が送出する`TypeError`/`ValueError`を`HTTPException`に変換する例外ハンドラを追加
   - `TestClient`を使ったエンドポイントテストを`tests/`に追加（`uv run pytest`で実行）

2. **データベース移行**
   - `uv add sqlalchemy aiosqlite asyncpg alembic`
   - `Todo`テーブル（`id`/`title`/`done`/`created_at`/`updated_at`）をSQLAlchemy 2.0スタイルで定義
   - 開発は`sqlite+aiosqlite:///./todo.db`、本番は`postgresql+asyncpg://...`を環境変数`DATABASE_URL`で切り替え
   - Alembicで初期マイグレーションを作成し、既存`todos.json`からの一度限りの移行スクリプトを用意
   - `TodoList`相当のロジックをリポジトリ層としてDBアクセスに置き換え（サービス層とエンドポイント層の分離を維持）

3. **コンテナ化とデプロイ**
   - マルチステージDockerfile（uvベース、非rootユーザー、ヘルスチェック付き）を作成
   - `.dockerignore`で`.venv`/`tests/`/`todos.json`等を除外
   - Renderにリポジトリを接続し、`main`へのpushで自動デプロイ（`render.yaml`でIaC管理）
   - GitHub Actionsで「テスト（`uv run pytest`）→ Dockerビルド検証」のCIゲートを構築し、ブランチ保護ルールでマージ条件にする
   - 本番DBはRenderの有料PostgreSQL、または30日失効に注意しつつ無料枠から開始し早期に有料化を判断

4. **仕上げ**
   - コールドスタート・データ永続性を実際に確認（再デプロイ後もデータが残るかテスト）
   - 必要に応じてRenderのDeploy Hookを使った明示的デプロイトリガーへ切替え（複数環境が必要になった場合）

## 6. 参考情報

各詳細レポートの「Sources」セクションに調査時点（2026年）の一次情報源を記載。特に以下は重要な参照先。

- [FastAPI Benchmarks（公式）](https://fastapi.tiangolo.com/benchmarks/)
- [FastAPI: SQL (Relational) Databases](https://fastapi.tiangolo.com/tutorial/sql-databases/)
- [Alembic公式ドキュメント](https://alembic.sqlalchemy.org/)
- [uv Docker統合ガイド（Astral公式）](https://docs.astral.sh/uv/guides/integration/docker/)
- [Render Deploy Hooks](https://render.com/docs/deploy-hooks)
- [Railway GitHub Actions連携](https://blog.railway.com/p/github-actions)
