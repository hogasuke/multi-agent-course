# Todoアプリ Web化 統合調査レポート

エージェントチーム（tmuxの3ペインで並列実行）による調査結果の統合レポート。

- チームメイト1: Webフレームワーク調査 → [詳細](research/web_framework.md)
- チームメイト2: データベース設計 → [詳細](research/database_design.md)
- チームメイト3: デプロイ戦略 → [詳細](research/deploy_strategy.md)

## 1. エグゼクティブサマリー

| 観点 | 推奨 | 理由（要約） |
|---|---|---|
| Webフレームワーク | **FastAPI** | 既存`TodoList`のCRUD＋検索＋統計という構造・型ヒントの徹底がPydanticと直接噛み合う。ASGIネイティブで非同期化も素直、CLAUDE.mdの技術スタックにも既に明記済み |
| データベース（開発） | **SQLite** | セットアップ不要、`uv run`だけで動き`pytest`（in-memoryモード）との相性も良い |
| データベース（本番） | **PostgreSQL** | MVCCによる高い同時実行性能、複数ワーカー・将来のユーザー管理を見据えた同時書き込み耐性が必要 |
| コンテナ化 | **Docker（マルチステージ、uvベース）** | 依存関係インストールとアプリコードコピーを分離しレイヤーキャッシュを効かせつつ、非rootユーザー・HEALTHCHECK込みで本番イメージを最小化 |
| デプロイ先 | **Railway（Hobby $5/月）を第一候補、Render（Starter $7/月〜）を次点** | 最小コスト・常時稼働重視ならRailway Hobby（コールドスタートなし、DB連携が簡単）、IaC・複数環境管理を重視するならRenderの`render.yaml`が有利。Fly.ioは無料枠廃止・CLI前提で学習コースの規模には過剰なため非推奨 |

3つの調査は独立して進めたが、推奨同士に矛盾はなく、**FastAPI + SQLAlchemy 2.0(async)/Alembic + Docker + Railway/Render** という一貫した技術スタックに収束した。

## 2. 現状（共通認識）

3チームメイトとも `src/todo.py` と `CLAUDE.md` を読み、以下を前提として調査した。

- `TodoList`クラスが`id`/`title`/`done`のCRUD（`add`/`list_all`/`complete`/`delete`）・検索（`search`）・統計（`get_stats`）をJSONファイル（同期I/O、全件書き込み、トランザクション性なし）で実装
- 型ヒントと日本語docstring（Args/Returns/Raises/Example）を徹底しており、外部依存はほぼゼロ
- 依存関係は`httpx`/`requests`/`pytest`のみで、Web層・ORM・非同期処理・DB・コンテナは未導入
- `uv`によるパッケージ管理、Python 3.14、`pip install`禁止
- ファイル破損時は`FileNotFoundError`/`JSONDecodeError`/`KeyError`を握りつぶして空リストにフォールバックする設計（＝データ消失を黙認する）

この現状認識が3つの調査結果で一致しており、後述の統合ロードマップの土台になっている。

## 3. 技術選定の整合性

- **FastAPI × データベース**：`TodoList`のCRUD操作はSQLAlchemy 2.0モデル＋FastAPIエンドポイントに1対1で対応させやすい（DB調査 4.3節に対応表あり）。DB調査が提案するSQLite（開発）/PostgreSQL（本番）の使い分けも、SQLAlchemy経由であれば方言差（`AUTOINCREMENT`、外部キー制約のデフォルト無効、`ALTER TABLE`の制限など）を吸収できる。
- **FastAPI × デプロイ**：デプロイ調査のDockerfileは`uvicorn src.main:app`を起動コマンドとしており、フレームワーク調査の推奨と直接整合している。非rootユーザー実行・HEALTHCHECK・exec形式CMD（グレースフルシャットダウン対応）もFastAPIの本番運用ベストプラクティスと一致。
- **データベース × デプロイ**：現状のJSONファイル永続化のままRender/Railwayへデプロイすると、再デプロイ・スケール時にコンテナのローカルファイルシステムがリセットされ**データが消える**。DB調査の結論（SQLite→PostgreSQL移行）とデプロイ調査の指摘が一致しており、Web化と同時にDB移行が事実上必須という共通の警告になっている。
- **3つの調査の推奨スキーマ・技術選定に矛盾はない**：DB調査が提案する`todos`テーブル（`id`/`title`/`done`/`created_at`/`updated_at`/`completed_at`）は、フレームワーク調査が推奨するPydanticスキーマ、デプロイ調査が想定するマネージドPostgreSQL（Railway/RenderでDB連携）といずれも整合する。

## 4. リスク・注意点（統合）

1. **JSON永続化のままのデプロイは危険**：Render/Railwayはコンテナのローカルファイルシステムが再デプロイ・スケール時にリセットされるため、`todos.json`は消失する。FastAPI化と同時にDB移行（SQLite→PostgreSQL）を行うこと。
2. **SQLite/PostgreSQLの方言差**：外部キー制約のデフォルト無効化（`PRAGMA foreign_keys=ON`が必要）、`ALTER TABLE`の制約変更の制限（Alembicの`render_as_batch=True`で対応）、`VARCHAR(200)`の長さがSQLiteでは強制されない点など、開発・本番で挙動が変わりうる部分はORM経由で吸収し、CIでもPostgreSQLに対するテストを定期実行してギャップを埋める。
3. **無料Web Serviceのコールドスタート**：Renderの無料枠は15分無操作でスピンダウンし、次リクエストで30〜60秒の遅延が起きる。デモ・発表前は有料プラン（Starter $7/月〜）への一時切替えも検討。
4. **Railwayは実質従量課金**：無料枠はクレジットカード不要のTrialで$5分の一回限りクレジットのみ。継続利用にはHobbyプラン（$5/月、利用量に応じた従量課金）が実質必須で、動かしっぱなしで気づかないうちにコストが増える可能性があるため予算アラートの設定を推奨する。
5. **エラー握り潰し挙動を踏襲しない**：現行`load()`はファイル破損時に静かに空リストへフォールバックするが、DB移行後はこの挙動を踏襲せず、接続失敗やマイグレーション未適用は明示的にエラーとして扱う（本番でのサイレントなデータ消失を防ぐ）。

## 5. 統合ロードマップ

1. **Webアプリ化の土台作り**
   - `uv add fastapi "uvicorn[standard]"`
   - `TodoList`の構造に対応するPydanticモデル（`TodoCreate`/`TodoResponse`）を定義（既存の空文字禁止・200文字制限バリデーションをスキーマ層へ移植）
   - `src/main.py`（または`api.py`）にAPIRouterを作成し、既存`TodoList`を依存性注入（`Depends`）で薄くラップするエンドポイントを実装（`POST /todos`、`GET /todos`、`PATCH /todos/{id}/complete`、`DELETE /todos/{id}`、`GET /todos/search`、`GET /todos/stats`、ヘルスチェック用`GET /health`）
   - `add`が送出する`TypeError`/`ValueError`を`HTTPException`に変換する例外ハンドラを追加
   - `TestClient`を使ったエンドポイントテストを`tests/`に追加（`uv run pytest`で実行）

2. **データベース移行**
   - `uv add sqlalchemy aiosqlite alembic`（本番用に`uv add asyncpg`）
   - `Todo`テーブル（`id`/`title`/`done`/`created_at`/`updated_at`/`completed_at`、`title`用・`done`用インデックス）をSQLAlchemy 2.0スタイルで定義
   - 開発は`sqlite+aiosqlite:///./dev.db`（テストは`sqlite+aiosqlite:///:memory:`）、本番は`postgresql+asyncpg://...`を環境変数`DATABASE_URL`で切り替え
   - Alembicで初期マイグレーションを作成（`render_as_batch=True`）し、既存`todos.json`からの一度限りの移行スクリプトを用意（ID採番の引き継ぎ、バリデーション再実行、UTF-8エンコーディングに注意）
   - `TodoList`相当のロジックをリポジトリ層としてDBアクセスに置き換え（サービス層とエンドポイント層の分離を維持）
   - ユーザー管理・タグ機能などの拡張は要件が具体化してから第二段階として追加する（YAGNI）

3. **コンテナ化とデプロイ**
   - マルチステージDockerfile（uvベース、非rootユーザー、HEALTHCHECK付き、exec形式CMD）を作成
   - `.dockerignore`で`.venv`/`tests/`/`todos.json`等を除外
   - Railway（最小コスト・常時稼働重視）またはRender（IaC・複数環境重視）にリポジトリを接続し、`main`へのpushで自動デプロイ
   - GitHub Actionsで「テスト（`uv run pytest`）→ Dockerビルド検証」のCIゲートを構築し、ブランチ保護ルールでマージ条件にする
   - 本番DBはRailway/RenderのマネージドPostgreSQLを利用し、予算・スケールの要件に応じて有料プランを選定

4. **仕上げ**
   - コールドスタート・データ永続性を実際に確認（再デプロイ後もデータが残るかテスト）
   - 必要に応じてDeploy Hook（Render）やRailway CLIを使った明示的デプロイトリガーへ切替え（テスト成功を厳密にデプロイ条件にしたい、または複数環境が必要になった場合）

## 6. 参考情報

各詳細レポートの「参考情報／Sources」セクションに調査時点（2026年）の一次情報源を記載。特に以下は重要な参照先。

- [FastAPI in Containers - Docker（公式）](https://fastapi.tiangolo.com/deployment/docker/)
- [Using uv with FastAPI（Astral公式）](https://docs.astral.sh/uv/guides/integration/fastapi/)
- [SQLModel - FastAPI and Pydantic（公式）](https://sqlmodel.tiangolo.com/tutorial/fastapi/)
- [Pricing | Render](https://render.com/pricing)
- [Pricing | Railway](https://railway.com/pricing)
- [Render vs Railway 2026 – Encore](https://encore.dev/articles/render-vs-railway)
