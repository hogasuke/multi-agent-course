FastAPIはまだ依存関係に含まれていないようですが、計画に記載の通り想定して進めます。現状のデータモデルを把握したので、レポートを出力します。

---

# Todoアプリ データ永続化方式 調査レポート

## 1. 現状のデータモデル

`src/todo.py` の `TodoList` クラスは、JSONファイル（デフォルト `todos.json`）を永続化先としている。

- データ構造: `{"todos": [...], "next_id": int}`
- 各Todoは辞書: `{"id": int, "title": str, "done": bool}`
- 書き込み操作（`add`, `complete`, `delete`）のたびにファイル全体を読み書き
- IDは削除しても再利用しない連番（アプリ側でインクリメント管理）
- タイトルは1〜200文字のバリデーションあり

この方式はシンプルだが、Webアプリ化を見据えると以下の課題がある。

- **同時アクセスに弱い**: ファイル全体を毎回書き換えるため、複数リクエストが同時に来るとレースコンディション（更新の取りこぼし）が起きうる
- **検索・集計が非効率**: `search` や `get_stats` は全件をPythonでループしており、件数が増えるとO(n)のメモリ走査になる
- **スキーマ保証がない**: JSONはアプリ側のコードでしか型・制約を守れない

---

## 2. SQLite vs PostgreSQL 比較

| 観点 | SQLite | PostgreSQL |
|---|---|---|
| コスト | 無料、サーバー不要（ファイル1つ） | 無料（OSS）だが、ホスティング費用が発生（マネージドDB利用時） |
| セットアップの手間 | ほぼゼロ（標準ライブラリ`sqlite3`で即利用可） | サーバー構築・接続設定・認証情報管理が必要 |
| スケーラビリティ | 単一ファイル・単一マシン前提。水平スケール不可 | レプリケーション、コネクションプーリング、クラスタ構成が可能 |
| 同時書き込み耐性 | 弱い（書き込みはファイルロックで直列化、WALモードでも同時書き込みは1つまで） | 強い（MVCCにより複数トランザクションが並行して書き込み可能） |
| 運用の手間 | バックアップ＝ファイルコピーで完結。運用監視はほぼ不要 | バックアップ・監視・チューニング・アップグレード等の運用コストが発生 |
| デプロイ環境との親和性 | ローカル開発・CI・組み込み用途に最適 | コンテナ/クラウド環境（複数インスタンス）でのWebアプリ本番運用に最適 |
| データ型・制約 | 動的型付けでやや緩い（型親和性ルール） | 厳密な型システム、CHECK制約、外部キー等が堅牢 |
| FastAPIとの組み合わせ | `aiosqlite` + SQLAlchemy(async) で利用可 | `asyncpg` + SQLAlchemy(async) で利用可。本番運用実績が豊富 |

**結論**: 個人開発・学習段階の単一プロセスならSQLiteで十分だが、複数Webサーバープロセス/インスタンスからの同時アクセスが発生する本格的なWebアプリでは、書き込みロック競合のリスクからPostgreSQLが望ましい。

---

## 3. 環境別の推奨

### 開発環境: SQLite

- セットアップ不要で即座に開発を開始できる（`uv add` で `aiosqlite` のみ追加すればよい）
- CI（pytest実行時）でも追加インフラ不要。テスト用DBをインメモリ（`:memory:`）にできるのも利点
- ファイルベースなので壊れたら削除して作り直せばよく、学習用途のイテレーション速度が高い

### 本番環境: PostgreSQL

- FastAPIは複数ワーカープロセス（Uvicorn/Gunicornのマルチワーカー）で動かすのが一般的であり、SQLiteの書き込み直列化はボトルネック・データ破損リスクになる
- 将来的なユーザー認証・複数ユーザー対応（Todoの所有者分離）を見据えると、PostgreSQLの堅牢な制約・インデックス機能が活きる

### 開発/本番でのDB使い分けについての注意

「開発はSQLite、本番はPostgreSQL」という使い分けは手軽だが、以下のリスクがあるため**学習目的を超えて本格運用するなら開発環境もPostgreSQLに統一することを推奨**する。

- SQLiteとPostgreSQLでSQL方言・型の挙動（例: `BOOLEAN`の扱い、`AUTOINCREMENT`と`SERIAL`の違い、大文字小文字の比較）に差異があり、開発時に気づかなかったバグが本番で初めて顕在化することがある
- SQLAlchemyのようなORMを使えば差異は緩和されるが、完全には消えない

本プロジェクトは学習目的の小規模アプリであるため、**まずは開発・本番ともにSQLiteで進め、複数ユーザー・複数プロセスでの運用が必要になった時点でPostgreSQLへ移行する**のが、学習コストと実用性のバランスとして妥当と考える。Docker等で本番相当の環境を用意できるなら、最初から両環境でPostgreSQLに統一してもよい。

---

## 4. 推奨スキーマ

現状の `id`, `title`, `done` に加え、Web化を見据えて以下を拡張案とする。

```sql
CREATE TABLE todos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,  -- PostgreSQLではSERIAL/GENERATED ALWAYS AS IDENTITYに置換
    title       VARCHAR(200) NOT NULL,
    done        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_title_not_empty CHECK (TRIM(title) <> '')
);

-- 完了/未完了での絞り込み・並び替えを高速化
CREATE INDEX idx_todos_done ON todos(done);
CREATE INDEX idx_todos_created_at ON todos(created_at);
```

PostgreSQL版（IDENTITY列・トリガーで`updated_at`自動更新する場合）:

```sql
CREATE TABLE todos (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    done        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_title_not_empty CHECK (TRIM(title) <> '')
);

CREATE INDEX idx_todos_done ON todos(done);

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_todos_updated_at
    BEFORE UPDATE ON todos
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
```

### カラム設計の補足

- `title`: 既存のバリデーション（1〜200文字、空白のみ不可）をDB制約にも反映。アプリ側のバリデーションは引き続き維持し、DB制約は最終防衛ラインとする
- `done`: 既存通りBOOLEAN
- `created_at` / `updated_at`: Webアプリでは「いつ作られたか」「いつ更新されたか」がソート・監査・UI表示に必須になるため追加
- 将来の拡張候補（今回は見送り、必要になれば追加）:
  - `user_id`（複数ユーザー対応時の所有者カラム、`users`テーブルへの外部キー）
  - `due_date`（期限）
  - `priority`（優先度）

---

## 5. マイグレーション方針

### 5.1 既存JSONデータからの移行

`todos.json` の `{"todos": [...], "next_id": ...}` 構造から、以下の手順でDBに取り込む。

1. JSONを読み込み、各todoの `id`, `title`, `done` をそのままINSERT
2. `created_at` / `updated_at` は移行時点では元データに存在しないため、移行実行時刻を一律で設定する（過去の作成日時は復元不可能である旨を許容する）
3. SQLiteの場合、`AUTOINCREMENT`のシーケンスを既存の `next_id - 1` まで進めておくことで、移行後も既存IDと衝突しない新規Todoを発行できる
   - SQLite: `INSERT INTO sqlite_sequence (name, seq) VALUES ('todos', <next_id - 1>);`（明示的に行を入れる、または最大IDのレコードを先に入れれば自動的にseqが追従する）
   - PostgreSQL: `SELECT setval(pg_get_serial_sequence('todos', 'id'), <next_id - 1>);`

移行用ワンショットスクリプト例（`uv run python` で実行する想定、本番反映前にバックアップ必須）:

```python
# scripts/migrate_json_to_db.py
import json
import sqlite3

def migrate(json_path: str, db_path: str) -> None:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT INTO todos (id, title, done) VALUES (?, ?, ?)",
        [(t["id"], t["title"], t["done"]) for t in data["todos"]],
    )
    conn.commit()
    conn.close()
```

### 5.2 スキーマバージョン管理（Alembic）

スキーマ自体の変更管理には **Alembic** の利用を推奨する。

- SQLAlchemyと組み合わせれば、SQLite/PostgreSQL双方に同一のマイグレーションスクリプトを適用できる（方言差はAlembicがある程度吸収する）
- 将来的なカラム追加（`due_date`等）やインデックス変更を、コードレビュー可能な形でバージョン管理できる
- 初期テーブル作成自体も最初のAlembicリビジョンとして記述し、JSONからのデータ移行は別途データ移行用スクリプト（上記5.1）として分離する（Alembicのマイグレーションにビジネスデータの移行ロジックを混在させると、スキーマ変更とデータ移行の責務が曖昧になるため）

導入コマンド例:

```bash
uv add alembic sqlalchemy
uv run alembic init alembic
```

学習段階で素早く反復したいだけであれば、最初は手書きの `CREATE TABLE` スクリプト（本レポート4節のSQL）で十分であり、スキーマ変更の頻度が増えてきた時点でAlembic導入を検討すればよい。
