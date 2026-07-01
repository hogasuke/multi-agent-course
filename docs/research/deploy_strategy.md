# デプロイ戦略調査レポート

## 前提の確認

現状の `src/todo.py` は `TodoList` クラス単体で、永続化は JSON ファイル（`todos.json`）への直接読み書きのみ。`pyproject.toml` にはまだ FastAPI・uvicorn が入っておらず、CLAUDE.md のロードマップ通り「FastAPI + uv」構成へ拡張する前提で本レポートを作成する。

**重要な制約**：JSON ファイル永続化はコンテナのローカルファイルシステムに書き込む方式のため、Render / Railway のようなコンテナ型 PaaS では **再デプロイやスケールでファイルが消える**（永続ディスクをアタッチしない限り）。本番運用するなら、DB 移行（`docs/research/database_design.md` 側の検討事項）か、有料の永続ボリュームの追加が事実上必須になる。この点は「推奨構成」で改めて触れる。

---

## 1. Dockerfile例（uvベース・マルチステージ）

Astral 公式の `uv` Docker ガイド（[docs.astral.sh/uv/guides/integration/docker](https://docs.astral.sh/uv/guides/integration/docker/)）の推奨パターンに、非rootユーザー化とヘルスチェックを加えたもの。

```dockerfile
# syntax=docker/dockerfile:1

# ---------- ビルドステージ ----------
FROM python:3.14-slim AS builder

# uv公式イメージからバイナリだけを取得（distrolessイメージを利用）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# 依存関係の定義ファイルだけ先にコピーしてキャッシュを効かせる
# （src/ を変更してもここは再実行されない）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# アプリ本体をコピーしてプロジェクト自体をインストール
COPY src/ ./src/
RUN uv sync --frozen --no-dev

# ---------- 実行ステージ ----------
FROM python:3.14-slim AS runtime

# 非rootユーザーで実行する
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app

# ビルドステージから仮想環境とアプリコードだけをコピー（ビルドツールは持ち込まない）
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH"
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`.dockerignore`（イメージ肥大化・キャッシュ無効化防止）:

```
.venv
__pycache__
*.pyc
.git
.pytest_cache
tests/
docs/
todos.json
.env
```

**ポイント**（[uv公式ガイド](https://docs.astral.sh/uv/guides/integration/docker/)、[Depot: Optimal Dockerfile for uv](https://depot.dev/docs/container-builds/optimal-dockerfiles/python-uv-dockerfile)より）
- `--no-install-project` で依存関係だけを先にインストールし、レイヤーキャッシュを最大化する（`src/` 変更時に `uv sync` を丸ごとやり直さない）。
- マルチステージ化で最終イメージにビルドツール（uv本体、コンパイラ類）を含めない。実測でシングルステージ比 60〜80% のサイズ削減が報告されている（[collabnix](https://collabnix.com/docker-multi-stage-builds-for-python-developers-a-complete-guide/)）。
- `python:3.14-slim` を採用（`python:3.14` 無印は800MB前後大きい）。
- 非rootユーザー実行とヘルスチェックは、Render/Railway がヘルスチェックエンドポイントを見てデプロイ成功判定するため必須級。

---

## 2. クラウドサービス比較表

| 項目 | Render | Railway | 参考: Fly.io |
|---|---|---|---|
| 無料枠 | ワークスペースごと月750時間の無料インスタンス時間。ただしFreeプランのWebサービスは**15分無操作でスピンダウン**し、次リクエストで約1分のコールドスタート（[Render公式記事](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)） | 明確な無料枠なし。Hobbyプラン $5/月〜が実質の最小コース（[Railway Docs](https://docs.railway.com/pricing/plans)） | 無料枠は縮小傾向、実質有料前提 |
| 最小有料コスト | Starter: 約$7/月〜（常時稼働・スピンダウンなし） | Hobby: $5/月（**使用量に応じた従量課金**で、$5分は月額に含まれる。超過分のみ追加課金）（[SaaSPricePulse](https://www.saaspricepulse.com/tools/railway)） | 従量課金、小規模なら数ドル/月 |
| 課金方式 | 固定プラン＋従量（ディスク/帯域等） | 完全従量制（CPU/RAM/ egress を秒単位で計測）（[makerkit.dev](https://makerkit.dev/pricing-calculator/railway)） | 完全従量制 |
| Docker対応 | ◎ Dockerfileを直接ビルド、または自動言語検出 | ◎ Dockerfileを直接ビルド、Nixpacksでの自動ビルドも可 | ◎ `fly.toml` + Dockerfile |
| 永続化（DB/ディスク） | 無料PostgreSQLは1GB・**作成30日で失効**（猶予14日）。永続ディスクは有料プランのみ（[kuberns.com](https://kuberns.com/blogs/render-postgres-pricing-setup-limits/)） | ボリューム（永続ディスク）が標準機能として利用可能、Postgresテンプレートも従量課金で常設 | ボリューム標準対応 |
| GitHub連携（Auto Deploy） | ◎ リポジトリ接続でpush時に自動デプロイ。`render.yaml`（Blueprint）でIaC管理可 | ◎ リポジトリ接続で自動デプロイ。「Wait for CI」設定でGitHub Actions完了を待って反映可能（[Railway Docs](https://docs.railway.com/deployments/github-autodeploys)） | GitHub Actions経由が基本 |
| CI/CD連携のしやすさ | Deploy Hook（Secret URLへのGET/POST）でGitHub Actionsから明示トリガー可能。または純粋にGit連携に任せてActionsはテストゲートのみに使う設計も容易（[Render Docs: Deploy Hooks](https://render.com/docs/deploy-hooks)） | 公式CLI（`railway up`）をActionsから叩く方式、または自動デプロイ＋Wait for CI。設定例が豊富（[Railway Blog](https://blog.railway.com/p/github-actions)） | `flyctl deploy` をActionsから実行 |
| 学習コストの体感難易度 | 低（管理画面がシンプル、ドキュメントも初心者向け） | 低〜中（従量課金の見積もりがやや分かりにくい） | 中（`fly.toml`の理解が必要） |

---

## 3. CI/CD連携方針（GitHub Actions）

推奨するのは「**テストゲート＋自動デプロイ**」の2段構成。

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - name: 依存関係のインストール
        run: uv sync --frozen
      - name: テスト実行
        run: uv run pytest
      - name: Dockerイメージのビルド検証
        run: docker build -t todo-app:ci .
```

デプロイの起動方法は2パターンあり、プロジェクト規模的には **(A) を推奨**。

- **(A) プラットフォームのGitHub連携に任せる**：Render/Railwayの管理画面でリポジトリを接続し、`main` へのpushで自動デプロイ。CI（上記ワークフロー）は「ブランチ保護ルールでmainへのマージ条件にする」役割に徹する。設定がシンプルで、学習プロジェクトのオーバーヘッドが最小。
- **(B) CIからデプロイを明示的にトリガーする**：CIジョブの最後に Render の Deploy Hook（`curl -X POST $RENDER_DEPLOY_HOOK_URL`）や Railway CLI（`railway up`）を呼ぶ。テスト成功を厳密なデプロイ条件にしたい場合や、複数環境（staging/production）を使い分けたい場合に有効。Railwayの「Wait for CI」設定を使えば、自動デプロイのままGitHub Actions完了を待たせることも可能。

いずれの場合も `RENDER_DEPLOY_HOOK_URL` / `RAILWAY_TOKEN` は GitHub Secrets に格納する。

---

## 4. 推奨構成とその理由

**推奨: Render（Docker環境、Starterプラン以上）+ GitHub連携による自動デプロイ**

理由:
1. **コスト**: 学習・個人プロジェクト規模ではRenderの無料枠（月750時間）で十分試せる。ただしスピンダウンによるコールドスタートが気になる場合、または常時稼働のTodoアプリとして使うならStarter（$7/月〜）で解決する。Railwayも悪くないが、完全従量課金は「動かしっぱなしにすると気づかないうちに増える」タイプのコスト構造で、学習用途では見積もりしやすいRenderの固定プランの方が扱いやすい。
2. **難易度**: DockerfileさえあればRenderは自動でビルド・デプロイしてくれ、`render.yaml` でインフラ定義をコードとして残せる（IaC）。CLAUDE.mdの「uvで管理・日本語コメント」という開発ルールとも相性がよく、Dockerfile内で完結する。
3. **CI/CD**: GitHub連携＋Deploy Hookの両方に対応しており、まずは(A)のシンプル運用から始めて、必要になったら(B)の厳密なゲート方式に切り替えられる拡張性がある。

**注意点（要フォローアップ）**:
- JSON永続化のままでは、RenderのGitデプロイ時にファイルシステムがリセットされるため **Todoデータが消える**。本番運用するなら、①Render無料Postgres（30日失効に注意）へのDB移行、②Renderの永続ディスク追加（有料）のいずれかが必要。`docs/research/database_design.md` の結論と合わせて、FastAPI移行と同時にDB永続化へ切り替えることを強く推奨する。
- `pyproject.toml` にまだ `fastapi` / `uvicorn` が入っていないため、Web化の初手として `uv add fastapi uvicorn` が必要（CLAUDE.mdのルール通り `pip install` は使わない）。

---

### Sources
- [Platforms with a real free tier for developers in 2026 - Render](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)
- [Render Postgres 2026: Pricing, Free Tier Limits](https://kuberns.com/blogs/render-postgres-pricing-setup-limits/)
- [Render Docs: Deploy Hooks](https://render.com/docs/deploy-hooks)
- [Railway Pricing Plans](https://docs.railway.com/pricing/plans)
- [Railway Free Tier 2026 - SaaSPricePulse](https://www.saaspricepulse.com/tools/railway)
- [Railway Pricing Calculator - makerkit.dev](https://makerkit.dev/pricing-calculator/railway)
- [Controlling GitHub Autodeploys - Railway Docs](https://docs.railway.com/deployments/github-autodeploys)
- [Using GitHub Actions with Railway - Railway Blog](https://blog.railway.com/p/github-actions)
- [Using uv in Docker - Astral](https://docs.astral.sh/uv/guides/integration/docker/)
- [Optimal Dockerfile for Python with uv - Depot](https://depot.dev/docs/container-builds/optimal-dockerfiles/python-uv-dockerfile)
- [Docker Multi-Stage Builds for Python Developers - Collabnix](https://collabnix.com/docker-multi-stage-builds-for-python-developers-a-complete-guide/)
