# Webフレームワーク比較レポート：FastAPI vs Flask vs Django

## 調査背景

Todoアプリを本格的なWebアプリケーションへ拡張するにあたり、Webフレームワークの選定を行う。
本プロジェクトの現状実装（`src/todo.py`）を確認したうえで、FastAPI・Flask・Djangoの3つを
「学習コスト」「非同期サポート」「エコシステム」「パフォーマンス」の4観点で比較し、
最適なフレームワークを提案する。

## 現状実装（src/todo.py）の分析

`TodoList` クラスはJSONファイルを永続化ストレージとするシンプルなCRUD実装であり、以下の特徴を持つ。

- **CRUD＋検索＋統計の明確な分離**：`add` / `list_all` / `complete` / `delete` に加え、
  `search`（キーワード部分一致検索）、`get_stats`（総数・完了数・未完了数・完了率の集計）という
  独立したメソッド群を持つ。これはWeb化した際に、それぞれが素直にRESTエンドポイント
  （`POST /todos`, `GET /todos`, `PATCH /todos/{id}/complete`, `DELETE /todos/{id}`,
  `GET /todos/search?q=...`, `GET /todos/stats`）に対応する構造である。
- **型ヒントの徹底**：`Optional[dict]` や `list[dict]` など戻り値・引数の型が明示され、
  日本語docstringでArgs/Returns/Raises/Exampleまで丁寧に記述されている。
  バリデーション（`TypeError`／`ValueError`）もメソッド内で明示的に行っている。
- **辞書ベースのデータ構造**：`todo` は `{"id": int, "title": str, "done": bool}` という
  素朴な辞書であり、まだPydanticやORMのモデルクラスには昇華されていない。
- **同期I/O**：`load`/`save` は素朴な同期のファイルI/O（`open`/`json.load`/`json.dump`）であり、
  非同期処理は一切導入されていない。

この「型ヒント徹底＋シンプルなデータ構造＋メソッド粒度の細かいCRUD」という設計は、
**型ヒットからそのままリクエスト/レスポンススキーマを導出できるフレームワーク**と特に相性が良い。
具体的には、`dict` ベースの `todo` をそのまま `Pydantic BaseModel`（もしくは `SQLModel`）に
昇格させるだけで、バリデーションロジック（空文字・200文字制限など）をスキーマ層に自然に移行でき、
既存のdocstringに書かれているRaises仕様がPydanticのバリデーションエラーとしてそのまま表現できる。

---

## 比較サマリー

| 観点 | FastAPI | Flask | Django |
|---|---|---|---|
| 学習コスト | 中（型ヒント・Pydanticの理解が必要） | 低（最小限のAPIで直感的） | 高（フルスタックゆえの規約・機能量が多い） |
| 非同期サポート | ◎ ネイティブ対応（async/await前提のASGI設計） | △ Flask 2.0以降で部分対応、土台はWSGIのまま | △ Django 5.x で改善が進むが、ORMは依然同期主体 |
| エコシステム | 中〜高（急成長中、API特化ライブラリが豊富） | 高（歴史が長く拡張ライブラリが豊富） | 最高（ORM・管理画面・認証などバッテリー同梱） |
| パフォーマンス | ◎ 非同期・Uvicornにより高スループット | ○ WSGIベースのため同期処理では標準的 | ○ フルスタックゆえのオーバーヘッドあり |

2026年時点の実測ベンチマークでも、FastAPI（Uvicorn 0.30系）は毎秒20,000リクエスト超・
中央値レイテンシ60ms未満を達成する例が報告されている一方、Flaskの同種計測では
毎秒数千リクエスト程度に留まるという結果が複数のレポートで一致している。

---

## 各フレームワークの詳細

### FastAPI

- **学習コスト**：型ヒントとPydanticによるスキーマ定義に慣れが必要だが、その分IDE補完や
  バリデーションの恩恵が大きく、中期的には開発速度が上がる。OpenAPI（Swagger UI）が
  自動生成される点も学習・デバッグの助けになる。本プロジェクトはすでに型ヒントと
  日本語docstringを徹底しているため、学習コストの実質的な上乗せは小さい。
- **非同期サポート**：Starlette上に構築されており、async/awaitがフレームワークの中核。
  DBアクセスや外部API呼び出しを非同期化しやすく、I/Oバウンドな処理に強い。
- **エコシステム**：SQLAlchemy 2.0の非同期対応やSQLModel、Pydantic v2（Rust製コアの
  pydantic-coreにより高速化）など周辺ツールの成熟が進んでいる。2026年時点でもFastAPI・
  SQLModelは継続的にリリースされており（Pydantic下限を2.9.0に引き上げ、Starlette 1.0.0への
  追随など）、活発にメンテナンスされている。Django程の「バッテリー同梱」ではないため、
  認証・管理画面などは別途ライブラリ選定（`fastapi-users`等）が必要。
- **パフォーマンス**：ベンチマークではPythonフレームワークの中でもトップクラス。
  非同期I/Oを活かせる構成であれば高いスループットが期待できる。

### Flask

- **学習コスト**：最小構成のマイクロフレームワークで、シンプルなAPIから始められるため
  学習コストは最も低い。ただし大規模化するとBlueprint設計やライブラリ選定を自前で
  行う必要があり、設計力が問われる。
- **非同期サポート**：Flask 2.0以降で async view をサポートするが、WSGIベースの土台の上に
  部分的に載せている形であり、FastAPIほどネイティブではない。非同期処理を多用する
  設計には不向き。
- **エコシステム**：歴史が長く拡張（Flask-SQLAlchemy、Flask-Login等）が豊富。ただし
  型安全性やスキーマバリデーションは標準では弱く、追加ライブラリでの補完が前提。
  `TodoList.add` が持つような明示的な型検証・エラー設計を活かすには、Pydanticなどを
  別途組み込む必要がある。
- **パフォーマンス**：同期処理では標準的な性能。非同期処理を活かした高負荷なAPIには
  向かない。

### Django

- **学習コスト**：ORM、管理画面、認証、フォームなどが同梱される「フルスタックフレームワーク」
  であり、規約や機能量が多いため学習コストは最も高い。ただし一度習得すれば大規模開発の
  生産性は高い。
- **非同期サポート**：Django 5.x でASGI対応・非同期ビューの改善が進んでいるが、
  ORM（Django ORM）は依然として同期が主体であり、フレームワーク全体としては
  同期処理を前提とした設計思想を引きずっている。
- **エコシステム**：管理画面・認証・ORM・国際化などが標準で揃っており、業務システムや
  CMS的な用途には非常に強い。サードパーティ製アプリ（django-rest-framework等）も豊富。
- **パフォーマンス**：フルスタックゆえのオーバーヘッドがあり、単純なAPIサーバーとしては
  FastAPIに劣る場合が多い。

---

## 本プロジェクトへの提案

**FastAPIの採用（継続利用）を推奨する。**

理由は以下の4点。

1. **既存スタックとの整合性**：本プロジェクトはCLAUDE.md／READMEで既にFastAPIを
   採用しており、Python 3.14 / uv という比較的新しい技術選定とも親和性が高い。
   フレームワーク移行によるリライトコストを避けられる。
2. **既存コード構造との噛み合わせの良さ**：`src/todo.py` はメソッド粒度が細かく
   （add/list_all/complete/delete/search/get_stats）、かつ型ヒントと詳細な
   docstring（Args/Returns/Raises）がすでに整備されている。これはFastAPIの
   「関数シグネチャ＋型ヒント→自動バリデーション＋OpenAPIドキュメント生成」という
   設計思想と極めて相性が良く、`dict` を `Pydantic BaseModel` に置き換えるだけで
   既存のバリデーションロジック（空文字禁止・200文字制限など）とエラー設計
   （TypeError/ValueError）をほぼそのままスキーマ層へ移植できる。
3. **非同期I/Oとの相性**：Todoアプリの拡張（複数ユーザー対応、DB連携、外部API連携など）を
   見据えると、非同期処理を前提にしたFastAPIの設計はスケールしやすい。特に将来的に
   JSON永続化からSQLite/PostgreSQL＋非同期SQLAlchemy（またはSQLModel）へ移行する際、
   FastAPIならエンドポイント定義を変えずに非同期化できる。
4. **型安全性と自動ドキュメント生成**：Pydanticによるスキーマ定義とOpenAPI自動生成は、
   チーム開発やAPI仕様の明確化において長期的な保守性に寄与する。2026年時点でも
   FastAPI・SQLModel・Pydantic v2は活発にメンテナンスされ続けており、Pydantic v2の
   Rust製コア（pydantic-core）によりバリデーション性能も向上している。

一方で、以下の点は留意する必要がある。

- Djangoのような「バッテリー同梱」の恩恵（管理画面・認証基盤など）はFastAPIには
  標準で無いため、必要に応じて `fastapi-users` や `SQLModel` などのライブラリを
  個別に選定する必要がある。
- Flaskのようなシンプルさは無いため、小規模なAPIのみで完結する場合はオーバースペックに
  なる可能性がある。

総合的に見て、Todoアプリを「本格的なWebアプリ」へ拡張する要件（非同期処理、
スケーラビリティ、型安全性）、既存の `TodoList` クラスの設計（型ヒント徹底・
メソッド粒度の細かいCRUD＋検索＋統計）、そしてプロジェクトの既存技術スタックを
踏まえると、**FastAPIが最適な選択**であると結論付ける。

---

## 参考情報（Web調査）

- [FastAPI vs Flask vs Django: Which to Choose in 2026 (Medium)](https://medium.com/@inprogrammer/fastapi-vs-flask-vs-django-which-to-choose-in-2026-c51b243174b5)
- [API Framework Performance Benchmark: FastAPI vs Flask vs Django (Medium)](https://medium.com/@afolabiifeoluwa06/api-framework-performance-benchmark-fastapi-vs-flask-vs-django-e767ad51574c)
- [Django vs Flask vs FastAPI in 2026 - Which to Choose (mecanik.dev)](https://mecanik.dev/en/posts/python-web-framework-comparison-2026-django-vs-flask-vs-fastapi/)
- [Which Is the Best Python Web Framework: Django, Flask, or FastAPI? (JetBrains Blog)](https://blog.jetbrains.com/pycharm/2025/02/django-flask-fastapi/)
- [Django vs Flask vs FastAPI 2026: Performance, Features & Which to Choose (Cipher Projects)](https://cipherprojects.com/blog/posts/django-vs-flask-vs-fastapi/)
- [SQLModel - FastAPI and Pydantic (公式ドキュメント)](https://sqlmodel.tiangolo.com/tutorial/fastapi/)
- [FastAPI Updates by Tiangolo - June 2026 (Releasebot)](https://releasebot.io/updates/tiangolo/fastapi)
