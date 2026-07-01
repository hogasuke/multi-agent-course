現状のデータモデルとpyproject.tomlを確認したので、レポートを出力します。

# Todoアプリ データベース設計調査レポート

## 1. 現状の把握

`src/todo.py` の `TodoList` は JSON ファイル（`todos.json`）を永続化層とし、以下のスキーマ相当のデータを保持している。

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | int | 連番ID（`next_id` で採番、削除されても再利用しない） |
| `title` | str | 1〜200文字、前後空白除去済み |
| `done` | bool | 完了フラグ |

`pyproject.toml` には現時点でDB関連の依存（SQLAlchemy等）は未追加。Webアプリ化にあたり、FastAPI + ORM + RDBMS構成への移行が必要になる。

## 2. SQLite vs PostgreSQL 比較表

| 観点 | SQLite | PostgreSQL |
|---|---|---|
| 動作形態 | ファイルベース（サーバー不要） | クライアント/サーバー型（要デーモン） |
| セットアップ | ゼロコンフィグ、`uv run` だけで即動く | Docker/マネージドサービスの用意が必要 |
| 同時書き込み | 弱い（ファイルロック、`WAL`モードでも書き込みは実質シングルライタ） | 強い（MVCCによる高い並行性） |
| スケール | 単一プロセス・小規模向け | 複数インスタンス・水平/垂直スケール向け |
| データ型 | 動的型付け（緩い） | 厳格な型システム（`SERIAL`, `TIMESTAMPTZ`, `JSONB`等） |
| トランザクション分離 | 基本的なACID対応 | 高度な分離レベル・行ロック制御 |
| バックアップ/レプリケーション | ファイルコピーのみ | ストリーミングレプリケーション、PITR等が充実 |
| 拡張機能 | 最小限 | 全文検索、JSONB、拡張機能（pg_trgm等）が豊富 |
| CI/テストでの扱いやすさ | 非常に容易（`:memory:` DBが使える） | コンテナ起動が必要 |
| ホスティングコスト | ほぼ無料（ファイルのみ） | マネージドDB利用時はコストが発生 |

## 3. 開発/本番での使い分け方針

- **開発環境・CI・ユニットテスト**: SQLite（`sqlite+aiosqlite:///./todo.db`、テストは `sqlite+aiosqlite:///:memory:`）を使用。セットアップ不要で高速に開発ループを回せる。
- **本番環境**: PostgreSQL（`postgresql+asyncpg://...`）を使用。同時アクセス・データ整合性・将来の機能拡張（全文検索、複数ユーザー対応等）に対応できる。
- **切り替えの仕組み**: SQLAlchemyの `Engine` はDB接続文字列（DSN）を環境変数（例: `DATABASE_URL`）で切り替えるだけで済むようにし、アプリケーションコード・ORMモデルはDBエンジンに依存しない書き方にする（SQLite固有の型やPostgreSQL固有の型は避けるか、`Enum`は`native_enum=False`にするなど互換性に配慮）。
- **注意点**: SQLiteは外部キー制約がデフォルト無効なため `PRAGMA foreign_keys=ON` を明示的に有効化すること。また、SQLiteでは `AUTOINCREMENT` の挙動やUPSERTの構文がPostgreSQLと異なるため、ORMのstatement-levelな記述に統一し、生SQLを避けるのが安全。

## 4. 推奨スキーマ

現状の `Todo` 構造（id/title/done）を土台に、Webアプリ化で最低限欲しくなる項目（作成・更新日時）を追加する。将来のユーザー管理は見据えつつ、現時点でオーバーエンジニアリングにならない最小限の拡張に留める。

```sql
-- todos テーブル
CREATE TABLE todos (
    id          INTEGER PRIMARY KEY,      -- SQLite: INTEGER PRIMARY KEY(rowid) / PostgreSQL: SERIAL or GENERATED ALWAYS AS IDENTITY
    title       VARCHAR(200) NOT NULL,     -- add()のバリデーション(1〜200文字)に対応
    done        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 検索(search)・完了率集計(get_stats)を高速化するインデックス
CREATE INDEX ix_todos_done ON todos (done);
CREATE INDEX ix_todos_title ON todos (title);  -- PostgreSQLではpg_trgmでLIKE '%keyword%'高速化も検討可
```

**SQLAlchemy 2.0 (async) モデル例:**

```python
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(DeclarativeBase):
    pass


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- `title`の200文字制約・空文字禁止は既存の `add()` バリデーションと同じ制約をDB側にも反映（アプリ層のバリデーションは維持しつつDB側でも保証）。
- `id`はSQLite/PostgreSQL双方でORMの自動採番に任せる形にし、`next_id`を手動管理する現行方式から脱却する（DBのAUTO INCREMENT/IDENTITYに委譲）。
- 将来の複数ユーザー対応が必要になった場合は `user_id`（FK）と複合インデックス `(user_id, done)` を追加する拡張ポイントとして想定しておく（現時点では実装しない）。

## 5. マイグレーション方針

- **ツール**: [Alembic](https://alembic.sqlalchemy.org/) を採用する。SQLAlchemyと親和性が高く、SQLite/PostgreSQL両方をサポートし、2026年時点でもFastAPI + SQLAlchemy構成のデファクトスタンダード。
- **構成**:
  - `alembic/env.py` でDB接続先を環境変数(`DATABASE_URL`)から取得し、開発（SQLite）・本番（PostgreSQL）で同一のマイグレーションスクリプトを共有する。
  - 非同期エンジンを使う場合は `env.py` 内で `run_sync` を使い同期的にマイグレーションを実行する構成にする（Alembic自体は同期実行が基本）。
- **運用フロー**:
  1. モデル変更後に `uv run alembic revision --autogenerate -m "説明"` でマイグレーションスクリプトを生成。
  2. 生成されたスクリプトを目視レビュー（autogenerateは列のリネームやSQLite特有の制約変更を誤検知することがあるため必須）。
  3. `uv run alembic upgrade head` をローカル（SQLite）・CI・本番（PostgreSQL）それぞれで適用。
  4. 既存の `todos.json` からのデータ移行は、初回マイグレーション後に一度限りの移行スクリプト（JSON読み込み→INSERT）を別途用意する。
- **SQLite特有の注意**: SQLiteは`ALTER TABLE`の制約変更（列の型変更・NOT NULL追加など）が限定的なため、Alembicは内部的に「新テーブル作成→データコピー→リネーム」のbatch modeで対応する。`env.py`で `render_as_batch=True` を設定すること。

## 6. まとめ

- 開発・CIはSQLite、本番はPostgreSQLという構成が2026年時点でも標準的かつ最もコストパフォーマンスが良い。
- SQLAlchemy 2.0（async対応）+ Alembicの組み合わせがFastAPIとの統合実績・エコシステムの成熟度で最有力。
- スキーマは既存の `id/title/done` を踏襲しつつ、`created_at`/`updated_at`を追加した最小限の拡張に留め、将来のユーザー管理拡張は現時点で実装しない（YAGNI）。

Sources:
- [SQL (Relational) Databases - FastAPI](https://fastapi.tiangolo.com/tutorial/sql-databases/)
- [How to Use SQLAlchemy with FastAPI](https://oneuptime.com/blog/post/2026-01-27-sqlalchemy-fastapi/view)
- [Using Alembic With FastAPI and PostgreSQL — No Bullshit Guide](https://medium.com/@rajeshpachaikani/using-alembic-with-fastapi-and-postgresql-no-bullshit-guide-b564ae89f4be)
- [Alembic for FastAPI and SQLAlchemy: The Complete Guide to Database Migrations](https://medium.com/@vamshimohan.b/alembic-for-fastapi-and-sqlalchemy-the-complete-guide-to-database-migrations-with-real-examples-c4b167d8b2bd)
- [FastAPI with Async SQLAlchemy, SQLModel, and Alembic | TestDriven.io](https://testdriven.io/blog/fastapi-sqlmodel/)
