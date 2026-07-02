# データベース設計調査レポート：Todoアプリの永続化方式

## 1. 調査目的と現状分析

現在のTodoアプリ（`src/todo.py`）は `TodoList` クラスがJSONファイル（`todos.json`）を丸ごと読み書きする方式で永続化している。本レポートでは、この実装をWebアプリ化するにあたり、SQLite / PostgreSQLへの移行方針・推奨スキーマ・ORM/マイグレーション戦略を提案する。

### 1.1 現状の実装（`TodoList`）の把握

| 項目 | 内容 |
|---|---|
| データ構造 | `todos: list[dict]`（各要素は `id`(int) / `title`(str) / `done`(bool)）＋ `next_id`(int) |
| 永続化 | `todos.json` に `{"todos": [...], "next_id": N}` として全件書き込み（`json.dump`、`ensure_ascii=False`） |
| 書き込みタイミング | `add` / `complete` / `delete` の**都度** `save()` を呼び、ファイル全体を再書き込み |
| ID採番 | `next_id` をアプリ側でインクリメント管理（削除してもID再利用しない） |
| 破損時の挙動 | `FileNotFoundError` / `JSONDecodeError` / `KeyError` を握りつぶして空リストに初期化（＝データ消失を黙認する設計） |
| 操作一覧 | `add(title)`：バリデーション付き追加（空文字・201文字以上・非str拒否）<br>`list_all()`：全件のシャローコピーを返却<br>`complete(todo_id)`：該当IDの`done`を`True`に更新、見つからなければ`None`<br>`delete(todo_id)`：該当ID削除、成否を`bool`で返却<br>`search(keyword)`：`title`に対する大文字小文字無視の部分一致検索<br>`get_stats()`：`total`/`done`/`pending`/`rate`を集計 |
| 依存関係 | `pyproject.toml` にはDB関連ライブラリ未追加（`httpx`, `requests` のみ）。python 3.14、パッケージ管理は `uv`、テストは `pytest` |

### 1.2 現状実装の課題（DB移行で解決したい点）

- **トランザクション性がない**：`save()`実行中にプロセスが落ちるとファイルが壊れる（部分書き込み）。同時アクセス時は競合・データロストの危険。
- **O(n)の全件走査**：`complete`/`delete`/`search`はリストの線形探索、`get_stats`も毎回全件集計。件数が増えるとWebアプリの応答性に影響。
- **同時書き込み耐性ゼロ**：複数プロセス/スレッドから同時に`save()`すると後勝ちで上書きされ、データが失われる（Webアプリでは複数リクエストが同時に来る前提が必須）。
- **エラー握り潰しによる暗黙のデータ初期化**：ファイル破損時に静かに空リストへ戻る挙動は本番運用では危険（気づかずデータが消える）。

これらはいずれも「RDBMS＋トランザクション＋インデックス」で自然に解決できるため、DB移行は妥当な方向性である。

---

## 2. SQLite vs PostgreSQL 比較

| 観点 | SQLite | PostgreSQL |
|---|---|---|
| アーキテクチャ | サーバーレス（ファイルベース、プロセス内埋め込み） | クライアント/サーバー型（別プロセスで常駐） |
| セットアップ | ライブラリ同梱のみで即利用可能。`uv run python` だけで動く | サーバーのインストール・起動・接続設定が必要（Docker等） |
| 同時書き込み性能 | 書き込みはロック単位。WALモードでも書き込みは実質シングルライタ | MVCCによる高い同時実行性能。行レベルロックで並行更新に強い |
| スケーラビリティ | 単一ファイル・単一ホスト前提、水平スケール不可 | レプリケーション、コネクションプーリング等でスケール可能 |
| データ型・機能 | 動的型付け、機能は最小限 | 厳密な型システム、JSONB、配列型、全文検索、CTE、ウィンドウ関数等が豊富 |
| トランザクション・整合性 | ACID対応（十分堅牢だが外部キー制約はデフォルト無効） | ACID対応、より高度な分離レベル制御が可能 |
| バックアップ・運用 | ファイルコピーで完結、単純 | pg_dump/WALアーカイブ等、専用の運用知識が必要 |
| クラウド対応 | マネージドサービスは限定的（Turso等） | RDS、Cloud SQL、Supabase等マネージドサービスが充実 |
| コスト | 追加コストなし | サーバー/マネージドサービスの費用が発生 |
| FastAPIとの親和性 | SQLAlchemy/SQLModelで即扱える、テストに最適 | 同上、本番運用実績が豊富。asyncpg採用でasync FastAPIとの相性も良い |

### 結論（要点）
- **SQLite**：セットアップ不要・ファイル一つで完結するため、**開発環境・テスト環境・CI**に最適。ただし複数リクエストからの同時書き込みが発生するWebアプリ本番運用には、書き込みロックの直列化とスケーラビリティの観点で不向き。
- **PostgreSQL**：MVCCによる高い同時実行性能、型の厳密さ、JSONB・全文検索などTodoアプリの将来拡張（タグ・全文検索等）にも有用な機能が揃い、マネージドサービスも充実しているため、**本番環境**に適している。

---

## 3. 環境別の推奨方針

### 3.1 開発環境
- **SQLiteを採用**。`uv run python` で即座に起動でき、Dockerやサーバー起動の手間がない。
- ローカルの `dev.db` ファイル一つで完結し、`.gitignore` に追加してチーム間の環境差異・機密データ混入を防ぐ。
- pytestでのテストは **SQLiteのin-memoryモード（`sqlite:///:memory:`）** を使い、テストごとにクリーンな状態を高速に用意する（`tests/test_todo.py` の既存テストもDB版に移行しやすい）。
- SQLiteは外部キー制約がデフォルト無効なため、接続時に `PRAGMA foreign_keys=ON` を明示的に有効化すること。

### 3.2 本番環境
- **PostgreSQLを採用**。マネージドサービス（Supabase、Amazon RDS、Cloud SQL、Renderの管理DB等）を利用し、バックアップ・冗長化・監視をサービス側に委譲する。
- 複数ユーザー・複数リクエストが同時にTodoを追加・更新するシナリオでも、行レベルロックとMVCCにより整合性を保ちながら高い同時実行性能を確保できる。
- 将来的な機能拡張（タグ・全文検索・共有Todoリスト等）にPostgreSQLの機能（JSONB、GINインデックス、`pg_trgm`）が活用できる。

### 3.3 環境差異を吸収する実装方針
- **SQLAlchemy 2.0（ORM）を採用**し、DB接続URLを環境変数（`DATABASE_URL`）で切り替える設計にする。
  - 開発：`sqlite+aiosqlite:///./dev.db`（テスト：`sqlite+aiosqlite:///:memory:`）
  - 本番：`postgresql+asyncpg://user:pass@host:5432/dbname`
- FastAPIは非同期フレームワークのため、**非同期エンジン（`create_async_engine`/`AsyncSession`）＋非同期ドライバ（開発: `aiosqlite`、本番: `asyncpg`）**の組み合わせが2026年時点でも定石。
- **Alembicによるマイグレーション管理**を導入し、SQLiteとPostgreSQL双方でスキーマ変更を一貫して適用する。SQLiteはほとんどの`ALTER TABLE`操作に対応していないため、`env.py`で `render_as_batch=True` を設定し、Alembicの「新テーブル作成→データコピー→リネーム」のbatchモードを使う（ただしFK制約があるテーブルへのbatch操作には制限があるため注意）。
- ORMレベルでは両DBに互換な型（`String`, `Integer`, `Boolean`, `DateTime`）を優先し、PostgreSQL固有機能（`JSONB`, 配列型等）はオプション拡張として分離する。ENUMは`native_enum=False`にする等、SQLite/PostgreSQL間の差異を吸収する。

---

## 4. 推奨スキーマ設計

現状の `TodoList`（id/title/done、単一ユーザー相当）を土台に、Webアプリ化で最低限必要になる項目（作成日時・更新日時・完了日時）を追加した**最小限の拡張**を第一段階として提案する。将来のユーザー管理・タグ機能は拡張ポイントとして別途示すが、YAGNIの観点から現時点での実装は必須としない。

### 4.1 第一段階：`todos` テーブル（現行データ構造への対応）

```sql
CREATE TABLE todos (
    id           INTEGER PRIMARY KEY,        -- SQLite: INTEGER PRIMARY KEY(rowid自動採番)
                                              -- PostgreSQL: GENERATED ALWAYS AS IDENTITY（SERIALの後継）
    title        VARCHAR(200) NOT NULL,      -- add()の1〜200文字バリデーションをDB側でも保証
    done         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL              -- complete()実行時刻を記録（doneのみでは失われる情報）
);

-- search(keyword) の部分一致検索を高速化
CREATE INDEX ix_todos_title ON todos (title);
-- get_stats() の完了/未完了集計、list_allのフィルタ表示を高速化
CREATE INDEX ix_todos_done ON todos (done);
```

**制約・型のマッピング（現行バリデーションとの対応）**

| 現行の`add()`バリデーション | DB側の対応 |
|---|---|
| `title`が空文字・空白のみは拒否 | アプリ層で`strip()`後に検証を維持しつつ、DB側は`NOT NULL`＋（可能なら）`CHECK (length(trim(title)) > 0)` |
| `title`が200文字超は拒否 | `VARCHAR(200)` で上限を保証（PostgreSQLは長さチェック制約、SQLiteは型的に緩いのでアプリ層検証必須） |
| `title`が非str（None等） | `NOT NULL` 制約 |
| `id`は`next_id`で手動採番、削除しても再利用しない | DBの`AUTO INCREMENT`/`IDENTITY`に委譲し、アプリ側の`next_id`管理を廃止（採番の一貫性はDBに保証させる） |
| `done`の既定値`False` | `DEFAULT FALSE` |

**注意**：SQLiteは動的型付けのため`VARCHAR(200)`の長さは強制されない（型アフィニティのみ）。文字数制約はアプリ層（Pydanticスキーマ等）でのバリデーションを主とし、DB制約は保険として位置づける。

### 4.2 SQLAlchemy 2.0 モデル例

```python
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(DeclarativeBase):
    pass


class Todo(Base):
    """Todoテーブルに対応するORMモデル。"""

    __tablename__ = "todos"
    __table_args__ = (
        Index("ix_todos_title", "title"),
        Index("ix_todos_done", "done"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

### 4.3 既存メソッドとクエリの対応関係

| 現行メソッド | DB移行後のクエリ相当 |
|---|---|
| `add(title)` | `INSERT INTO todos (title) VALUES (:title)`（`id`/`created_at`/`updated_at`はDB側デフォルト） |
| `list_all()` | `SELECT * FROM todos ORDER BY id` |
| `complete(todo_id)` | `UPDATE todos SET done=TRUE, completed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=:id`（更新件数0なら`None`相当を返す） |
| `delete(todo_id)` | `DELETE FROM todos WHERE id=:id`（削除件数で成否判定） |
| `search(keyword)` | `SELECT * FROM todos WHERE title LIKE '%' \|\| :keyword \|\| '%' COLLATE NOCASE`（PostgreSQLは`ILIKE`、または`ix_todos_title`＋`pg_trgm`で高速化） |
| `get_stats()` | `SELECT COUNT(*), SUM(CASE WHEN done THEN 1 ELSE 0 END) FROM todos`（1クエリで集計、アプリ側でのゼロ除算回避は維持） |

### 4.4 拡張ポイント（第二段階・将来のユーザー管理/タグ機能を見据える場合）

現時点の要件（単一ユーザー・単一リストのTodo管理）では不要だが、Webアプリとして複数ユーザー対応が決まった段階で以下を追加する設計にしておくと移行がスムーズ。

- `users` テーブル（`id`, `email` UNIQUE, `hashed_password`, `created_at`）を追加し、`todos.user_id`（FK, NOT NULL）を付与。
- 複合インデックス `todos(user_id, done)` でユーザーごとの未完了一覧取得を高速化。
- タグ機能が必要になれば `tags` / `todo_tags`（多対多中間テーブル）を追加し、`UNIQUE(user_id, name)` でユーザー内のタグ名重複を防止。
- 全文検索を強化する場合、PostgreSQLの`tsvector`＋`GIN`インデックス、またはSQLiteのFTS5拡張を検討。

これらは現行の`TodoList`の責務を超える機能拡張であるため、**第一段階の`todos`単体スキーマをまず実装し、要件が具体化してから第二段階に着手する**のが妥当（YAGNI）。

---

## 5. JSON → DB 移行時の注意点

1. **一度限りの移行スクリプトを用意する**：初回マイグレーション（`alembic upgrade head`）でテーブルを作成した後、`todos.json`を読み込み`INSERT`する専用スクリプトを別途作成する。既存の`id`値をそのまま引き継ぐか、採番し直すかを事前に決める（引き継ぐ場合はPostgreSQLの`IDENTITY`シーケンスを`SELECT setval(...)`で移行後の最大ID+1に合わせる必要がある）。
2. **`next_id`の扱い**：現行実装は削除してもIDを再利用しない仕様。DBのAUTO INCREMENT/IDENTITYも同様に「削除されたIDを再利用しない」ため、移行後もこの挙動は自然に維持される。
3. **バリデーション済みデータでも再検証する**：JSON側で不正なデータ（空文字titleや201文字超）が万一紛れ込んでいた場合に備え、移行スクリプトでもアプリ層と同じバリデーションを通してからINSERTする。
4. **文字エンコーディング**：現行は`ensure_ascii=False`でUTF-8の日本語タイトルをそのまま保存している。SQLite/PostgreSQLともにデフォルトでUTF-8を扱えるが、接続文字列・DBの`ENCODING`設定（PostgreSQLは`CREATE DATABASE ... ENCODING 'UTF8'`）を明示しておく。
5. **移行のロールバック手段を確保**：移行後もしばらくは`todos.json`をバックアップとして保持し、DB側に問題があれば旧実装に戻せるようにする（本番切り替え前にステージング環境で移行スクリプトを検証）。
6. **エラー握り潰しの挙動を踏襲しない**：現行の`load()`は破損時に静かに空リストへフォールバックするが、DB移行後はこれを踏襲せず、接続失敗やマイグレーション未適用は明示的にエラーとして扱う（本番でのサイレントなデータ消失を防ぐ）。

---

## 6. 移行・運用ロードマップ（推奨）

1. **現状**：`pyproject.toml`にDB関連依存を追加する（`uv add sqlalchemy aiosqlite alembic`、本番用に`uv add asyncpg`）。
2. **開発フェーズ**：SQLiteで`todos`テーブルを実装・検証。Alembicでマイグレーション履歴の管理を開始（`render_as_batch=True`）。
3. **移行スクリプト作成**：`todos.json`→DBへの一度限りの移行スクリプトを実装し、開発環境で動作確認。
4. **本番リリース前**：PostgreSQL（マネージドサービス）に同一マイグレーションを適用し、動作検証（型・制約の差異、IDENTITY採番方式、文字コード）を実施。
5. **本番運用開始**：PostgreSQLを正とし、SQLiteは開発・CIテスト専用として維持する。

---

## 7. まとめ

- **開発環境はSQLite、本番環境はPostgreSQL**という使い分けが、セットアップの手軽さと本番の堅牢性・同時実行性能を両立する現実的な選択である。
- 推奨スキーマは現行の`TodoList`（id/title/done）を忠実に踏襲した**`todos`単体テーブル**（`created_at`/`updated_at`/`completed_at`を追加）を第一段階とし、`title`用・`done`用のインデックスで`search()`/`get_stats()`を高速化する。
- ユーザー管理・タグ等の拡張は要件が具体化してから第二段階として追加する（YAGNI）。
- SQLAlchemy 2.0（非同期：`aiosqlite`/`asyncpg`）＋Alembic（`render_as_batch=True`）の組み合わせが、FastAPIとの統合実績・DB切り替えの容易さの両面で最有力。
- JSON→DB移行では、ID採番方式の引き継ぎ、バリデーション再実行、エラー握り潰し挙動の見直しに注意する。
