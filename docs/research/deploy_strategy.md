# Docker化・PaaSデプロイ調査レポート

## 1. 前提：現状のプロジェクト構成

- `src/todo.py` は JSON ファイルを永続化先とする `TodoList` クラスのみで、Web フレームワーク（FastAPI 等）はまだ `pyproject.toml` に追加されていない（現状の依存は `httpx`, `requests`, `pytest` のみ）。
- パッケージ管理は `uv`、Python は `>=3.14` を要求。
- 今後 FastAPI でWeb化し、インターネット公開する計画。

→ Docker化・PaaS選定は「FastAPI + uv」を前提に検討する。

## 2. uvベースのPythonアプリ向けDockerfile方針

### 方針
- **公式 `uv` Dockerイメージ**（`ghcr.io/astral-sh/uv`）をビルダーとして使い、マルチステージビルドで本番イメージを軽量化する。
- 依存関係のインストール（`uv sync`）とアプリコードのコピーを別レイヤーに分け、コード変更時の再ビルドを高速化する。
- `--frozen` で `uv.lock` を厳格に使用し、ビルドの再現性を保証する。
- 本番では `dev` 依存（pytest等）を除外（`--no-dev`）。
- 非rootユーザーで実行し、`uvicorn` をプロセスマネージャなしで直接起動（PaaS側がプロセス監視するため）。

### サンプル Dockerfile

```dockerfile
# --- ビルドステージ ---
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 依存関係だけを先にインストール（キャッシュを効かせる）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# アプリ本体をコピーしてインストール
COPY . .
RUN uv sync --frozen --no-dev

# --- 実行ステージ ---
FROM python:3.14-slim-bookworm AS runtime

WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"

# 非rootユーザーで実行
RUN useradd -m appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

補足:
- `PORT` 環境変数をPaaS側が指定してくる場合があるため、本番では `--port ${PORT:-8000}` のようにシェル経由で展開するか、起動スクリプトで吸収する。
- `.dockerignore` に `__pycache__/`, `.venv/`, `tests/`, `docs/`, `*.json`（todos.json等のローカルデータ）を入れてイメージを汚さない。

## 3. 主要PaaS比較表

| 項目 | Render | Railway | （参考）Fly.io |
|---|---|---|---|
| **無料枠** | 月750時間の無料インスタンス時間。Webサービスは15分非アクセスでスピンダウンし、次回アクセス時に約1分かけて再起動。クレジットカード不要 | 新規登録時$5の一回限りのトライアルクレジット（30日）。以降は月$1分の無料クレジットのみで実質有料 | 無料枠は段階的に縮小しており、実質クレジットカード前提 |
| **有料プラン目安** | Starter $7/月（512MB RAM）〜Pro $85/月（4GB/2CPU） | Hobby $5/月（$5分の使用クレジット込み、超過分は従量課金） | 使用量課金（VM時間・帯域ベース） |
| **導入難易度** | Dockerfile or 自動ビルド検出（Python/Node等）に対応。管理画面がシンプルで設定項目も少ない | Dockerfile or Nixpacks自動ビルド。CLIが強力でローカル⇔クラウドの差が小さい | `fly.toml` での設定が必要でやや学習コストが高い |
| **CI/CD連携（GitHub Actions等）** | GitHub連携でpush時に自動デプロイ。Actions経由のWebhookデプロイも簡単 | GitHub連携で自動デプロイ。Railway CLIをActionsに組み込みやすい | `flyctl deploy` をActionsに組み込む形。やや手数が多い |
| **DB（Postgres等）** | 無料DBは1GB・作成から30日で失効（猶予14日） | 同一プロジェクト内にPostgresを簡単追加、使用量課金 | Postgres相当はFly Postgres（有料） |
| **スピンダウンの影響** | 無料枠は非アクセス時に停止→コールドスタートあり | 基本的に常時起動（クレジット消費に直結） | 常時起動（課金対象） |

## 4. このプロジェクトへの推奨デプロイ先

**結論：Render（無料枠）を推奨**

理由:
1. **学習目的・個人プロジェクトとの相性**：このプロジェクトは「マルチエージェントコースの実習」用であり、本番の高可用性は不要。Renderの無料枠（クレジットカード不要、月750時間）は学習用途に最適。
2. **Dockerfile運用がそのまま使える**：上記で用意したDockerfileをそのまま`render.yaml`もしくはダッシュボードから指定するだけでデプロイ可能。uvベースの構成と相性が良い。
3. **GitHub連携が容易**：mainブランチへのpushで自動デプロイでき、追加のCI/CD構築コストが低い。GitHub Actions側でテスト（`uv run pytest`）→Render側で自動デプロイ、という分担がシンプルに組める。
4. **コールドスタートは許容範囲**：無料枠のスピンダウン（15分非アクセス→約1分で再起動）はTodoアプリのデモ用途であれば実用上問題ない。

Railwayはクレジット制で実質的に「無料」期間が短く（トライアル後は月$1分のみ）、継続利用には早期に課金が発生するため、長期の学習用途には不向き。

## 5. 導入ロードマップ（次の一歩）

1. **FastAPI化**：`uv add fastapi uvicorn` を実行し、`main.py` に `TodoList` を使ったREST API（GET/POST/PUT/DELETE）を実装。
2. **Dockerfile追加**：上記サンプルを `Dockerfile` として配置し、ローカルで `docker build` → `docker run` して動作確認。
3. **GitHub Actionsでテスト自動化**：push時に `uv run pytest` を実行するワークフローを追加（既存のCI構成があれば拡張）。
4. **Renderにアカウント作成・GitHubリポジトリ連携**：Web ServiceとしてリポジトリをImportし、Dockerfileを検出させてデプロイ。
5. **環境変数・データ永続化の検討**：現状はJSONファイル永続化のため、Render上ではコンテナ再起動でデータが消える点に注意。本格運用する場合は次のステップでRender Postgres（無料枠1GB）への移行を検討。
6. **公開後の動作確認**：デプロイURLでAPIの主要エンドポイントを叩いて疎通確認。

Sources:
- [Platforms with a real free tier for developers in 2026](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)
- [Pricing | Render](https://render.com/pricing)
- [Render Pricing 2026: Plans, Costs and Alternatives • Kuberns](https://kuberns.com/blogs/render-pricing/)
- [Pricing Plans | Railway Docs](https://docs.railway.com/pricing/plans)
- [Free Trial | Railway Docs](https://docs.railway.com/pricing/free-trial)
- [Railway Pricing & Plans (June 2026) | Compare Costs & Features - SaaSworthy](https://www.saasworthy.com/product/railway-app/pricing)
