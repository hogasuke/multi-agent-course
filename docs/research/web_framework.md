# Webフレームワーク比較調査レポート：Todoアプリの本格Web化に向けて

## 1. 現状把握

`src/todo.py` の `TodoList` クラスは以下の特徴を持つ、フレームワーク非依存のピュアPythonロジックです。

- JSON ファイルへの読み書き（`load`/`save`）による永続化
- `add`/`list_all`/`complete`/`delete`/`search`/`get_stats` という明確なCRUD＋検索・集計API
- 型ヒント（`Optional[dict]` など）と日本語docstringを徹底
- 外部依存ゼロ（`json`と標準ライブラリのみ）

このクラスをそのまま「サービス層」として再利用し、HTTP経由で叩けるAPIサーバーを被せる、という拡張が最も自然な流れです。CLAUDE.mdの技術スタック欄にも既に `FastAPI` が明記されており、`uv`（pip不使用）・`pytest` という開発ルールとの親和性も考慮する必要があります。

## 2. 比較表

| 観点 | FastAPI | Flask | Django |
|---|---|---|---|
| 学習コスト | 型ヒント・async/await・Pydanticの前提知識が必要でやや高いが、型を書く習慣があれば短時間で習熟 | 最も低い。書いたものがそのまま動く「マイクロフレームワーク」 | 高い。ORM・設定・アプリ構成など独自の作法が多く、覚える範囲が広い |
| 非同期サポート | ASGIネイティブ。`async def`が第一級市民 | WSGIベース。Flask 2.0以降`async def`ビューは書けるが本質は同期 | Django 5.x で`async def`ビュー・ASGI対応が進んだが、ORMは依然同期が中心 |
| エコシステム | 若いが急成長中。API特化のライブラリ（Pydantic, SQLModel等）は充実、汎用ライブラリはFlask/Djangoに劣る | 10年以上の蓄積があり、Flask-Login/Flask-SQLAlchemy/Flask-Admin等が豊富 | 最も広い。認証・管理画面・ORM・フォームなど「フルスタック」機能が標準搭載 |
| パフォーマンス | Uvicorn上で高スループット（ベンチマークではFlaskの数倍〜、単純なJSON応答で15,000〜20,000 req/s規模の報告あり） | 同期WSGIとしては妥当な性能だが、単純ベンチでFastAPIに数倍の差をつけられることが多い | ミドルウェア・ORM・シリアライズのオーバーヘッドで3者中もっとも遅くなりがちだが、DBアクセスが支配的な実運用では差は縮まる |

*(数値は2026年時点の各種ベンチマーク記事に基づく目安であり、実運用ではDBクエリ等が支配的でフレームワーク差は縮小する点に注意)*

## 3. 各観点の詳細

### 学習コスト
Flaskは「見たままが動く」ため最初の一歩は最も軽いですが、認証・バリデーション・シリアライズなどを自前かFlask拡張で組み立てる必要があり、後工程の学習コストが分散して発生します。Djangoは`models.py`・`settings.py`・`urls.py`・マイグレーションなど独自の作法を最初にまとめて覚える必要があり、初期コストが最も高いです。FastAPIは型ヒント＋Pydanticモデル＋`async/await`という前提知識が要りますが、`todo.py`は既に型ヒントを徹底しているため、このプロジェクトにとっての追加コストは実質「Pydanticモデルの書き方」と「async/awaitの基本」程度に収まります。

### 非同期サポート
JSON永続化のような単純なI/Oでは同期でも十分ですが、将来DBやキャッシュ、外部APIとの連携を見据えるとASGIネイティブなFastAPIが最も素直に非同期化できます。DjangoもASGI対応が進みましたが、ORM層は依然同期が主体で「部分的な非同期」という中途半端さが残ります。Flaskは今なお基本はWSGI/同期という位置づけです。

### エコシステム
本格的な会員機能・管理画面・複雑なフォームなどフルスタックの要件が今後増えるならDjangoの豊富な標準機能とエコシステムが有利です。逆に「Todoの操作をAPIとして公開する」というスコープに留まるなら、FastAPIのPydantic/SQLModelエコシステムで十分要件を満たせます。Flaskはその中間で、必要な機能をFlask拡張として個別に足していく形になります。

### パフォーマンス
単純なJSON応答というワークロードにおいてはFastAPI（Uvicorn/ASGI）が3者中もっとも高いスループットを示す報告が多く、DjangoはORMとミドルウェアのオーバーヘッドで見劣りする傾向にあります。ただし今回のTodoアプリはJSONファイルI/Oが律速するため、フレームワーク単体の性能差が体感できるほどのボトルネックになる可能性は低い点は留意してください。

## 4. 推奨：FastAPI

このプロジェクトには **FastAPI** を推奨します。理由は以下の3点です。

1. **既存コードとの相性**: `TodoList`クラスはCRUD＋検索＋統計という「API向け」の形にすでに整理されており、型ヒントを徹底したスタイルはFastAPI/Pydanticの流儀とそのまま噛み合います。`add`が投げる`TypeError`/`ValueError`もFastAPIの例外ハンドラでHTTPエラーに変換しやすく、書き換えがほぼ不要です。
2. **CLAUDE.mdとの整合性**: プロジェクトの技術スタックに既にFastAPIが明記されており、追加の合意形成コストがありません。
3. **スコープに対する適正規模**: 会員認証や管理画面などフルスタック要件が今のところ見当たらないため、Djangoはオーバースペックです。一方Flaskは自由度が高い分、バリデーションやOpenAPIドキュメント生成を自分で組む必要があり、`TodoList`が持つ型情報を活かしきれません。FastAPIならPydanticモデル（例: `TodoCreate`, `TodoResponse`）を`TodoList`のdictスキーマにほぼ1対1で対応させるだけで、リクエストバリデーションと自動ドキュメント（Swagger UI）が無料で手に入ります。

### 移行の具体イメージ
- `TodoList`インスタンスをアプリ起動時に1つ生成し、FastAPIの依存性注入（`Depends`）で各エンドポイントに渡す
- `POST /todos`→`add`、`GET /todos`→`list_all`、`PATCH /todos/{id}/complete`→`complete`、`DELETE /todos/{id}`→`delete`、`GET /todos/search`→`search`、`GET /todos/stats`→`get_stats`と1対1でマッピング可能
- `add`が送出する`TypeError`/`ValueError`は`@app.exception_handler`または`try/except`で`HTTPException(422)`等に変換
- 将来的にJSONファイルからDBへ移行する場合も、サービス層（`TodoList`相当）とエンドポイント層が分離されているため、影響範囲をルーティング層に閉じ込めやすい

Sources:
- [Python Flask vs FastAPI vs Django: Framework Comparison 2026](https://dasroot.net/posts/2026/02/python-flask-fastapi-django-framework-comparison-2026/)
- [Django vs Flask vs FastAPI in 2026 - Which to Choose](https://mecanik.dev/en/posts/python-web-framework-comparison-2026-django-vs-flask-vs-fastapi/)
- [FastAPI vs Django vs Flask in 2026: Choosing the Right Python Web Framework](https://developersvoice.com/blog/python/fastapi_django_flask_architecture_guide/)
- [FastAPI vs Flask vs Django: Which to Choose in 2026 | Medium](https://medium.com/@inprogrammer/fastapi-vs-flask-vs-django-which-to-choose-in-2026-c51b243174b5)
- [FastAPI vs Flask vs Django: Which to Choose in 2026 - Zestminds](https://www.zestminds.com/blog/fastapi-vs-django-vs-flask/)
- [API Framework Performance Benchmark: FastAPI vs Flask vs Django | Medium](https://medium.com/@afolabiifeoluwa06/api-framework-performance-benchmark-fastapi-vs-flask-vs-django-e767ad51574c)
- [FastAPI vs Flask: 4x Faster + Auto Docs [2026] - Tech Insider](https://tech-insider.org/fastapi-vs-flask-2026/)
- [Django vs Flask vs FastAPI 2026: Performance, Features & Which to Choose](https://cipherprojects.com/blog/posts/django-vs-flask-vs-fastapi/)
- [Benchmarks - FastAPI (official)](https://fastapi.tiangolo.com/benchmarks/)
- [FastAPI vs Flask vs Django: What Actually Matters in 2026 | Medium](https://medium.com/@rameshkannanyt0078/fastapi-vs-flask-vs-django-what-actually-matters-in-2026-83e47ab1daf0)
- [Flask vs FastAPI vs Django: Which Framework to Choose in 2026?](https://webandcrafts.com/blog/django-vs-flask-vs-fastapi)
