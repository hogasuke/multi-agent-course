# デプロイ戦略調査レポート：Todoアプリのコンテナ化とクラウドデプロイ

## 1. 調査の目的

本プロジェクト（FastAPI + uv構成のTodoアプリ）を本格的なWebアプリへ拡張するにあたり、Docker化の方法と、Render・Railway・Fly.ioを中心としたクラウドサービスへのデプロイ方法について、コスト・難易度・CI/CD連携の観点から調査した（2026年7月時点の情報）。

---

## 2. Docker化の方法

### 2.1 基本方針

FastAPI公式ドキュメントおよびuv公式ガイドでは、以下の構成が推奨されている。

- **マルチステージビルド**：ビルド用ステージと実行用ステージを分離し、イメージサイズを削減
- **uvの活用**：`ghcr.io/astral-sh/uv` の公式イメージから `uv` バイナリのみをコピーし、`uv sync --frozen` で依存関係を再現性高くインストール
- **非rootユーザーでの実行**：セキュリティ強化のためコンテナ内で専用ユーザーを作成して実行
- **HEALTHCHECK命令**：コンテナのヘルスチェックエンドポイント（例：`/health`）を用意し、Docker/オーケストレータが死活監視できるようにする
- **exec形式でのCMD**：`uvicorn`のグレースフルシャットダウンとlifespanイベントを正しく機能させるため、シェル形式ではなくexec形式で起動コマンドを記述する

### 2.2 Dockerfileの例（本プロジェクト向け）

```dockerfile
# ---- ビルドステージ ----
FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache --no-dev

# ---- 実行ステージ ----
FROM python:3.14-slim
RUN useradd --create-home appuser
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src/ ./src/
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
HEALTHCHECK --interval=30s --timeout=3s CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

依存関係のコピーとインストールをアプリコードのコピーより前に行うことで、コード変更時にDockerのレイヤーキャッシュが効き、ビルド時間を短縮できる。

### 2.3 docker-compose（ローカル開発用）

DB（PostgreSQL等）を導入する場合は `docker-compose.yml` でアプリとDBをまとめて起動する構成が定番。本番のRender/RailwayではマネージドDBを使うため、compose環境はあくまでローカル検証用として位置づけるのが良い。

---

## 3. クラウドサービス比較

### 3.1 Render

| 項目 | 内容 |
|---|---|
| 無料枠 | Web Service 750時間/月、100GB送信帯域、ビルド500分/月。ただし15分アイドルでスリープし、コールドスタートに30〜60秒かかる |
| 有料プラン | Starter $7/月（常時稼働・共有CPU）、Standard $25/月、Pro $85/月〜（専有CPU） |
| 難易度 | 低い。GitHubリポジトリ連携＋`render.yaml`（Infrastructure as Code）または管理画面のみで、Dockerfileを検出して自動ビルド・デプロイ可能 |
| CI/CD | GitHubへのpushで自動デプロイ（Auto Deploy）が標準機能。PRごとのプレビュー環境も対応 |
| DB | Render Postgresをマネージドサービスとして提供（無料枠あり、期限付き） |

### 3.2 Railway

| 項目 | 内容 |
|---|---|
| 無料枠 | クレジットカード不要のTrialプランで$5分の一回限りクレジット |
| 有料プラン | Hobby $5/月（$5分の利用クレジット込み、使用量に応じた従量課金）、Pro $20/月〜 |
| 難易度 | 非常に低い。GitHub連携でDockerfileまたはNixpacks（自動言語検出）によりビルド。設定はほぼGUIで完結 |
| CI/CD | pushで自動デプロイ。環境ごとのブランチデプロイやRailway CLIによるCI連携も容易 |
| DB | PostgreSQL/MySQL/Redis等をワンクリックでプロビジョニング可能、同一プロジェクト内で環境変数が自動連携される |

### 3.3 Fly.io

| 項目 | 内容 |
|---|---|
| 無料枠 | **2024年に恒常無料枠を廃止済み**。新規アカウントは$5分のトライアルクレジットのみで、Machineはアイドル5分で自動停止する評価用途向け。2026年時点で永続無料枠は存在しない |
| 有料プラン | 従量課金制。最小構成（shared-cpu-1x、256MB RAM）を常時稼働させると約$1.94/月〜。API＋Postgresの一般的な本番構成では$13〜$20/月程度 |
| 難易度 | 中程度。`flyctl launch`でDockerfileから自動的に`fly.toml`を生成できるが、リージョン・ボリューム・スケーリング設定をCLIやTOMLで明示的に管理する必要があり、Render/Railwayに比べ運用の学習コストがやや高い |
| CI/CD | GitHub Actions用の公式Action（`flyctl deploy`）が提供されており、pushトリガーのデプロイをワークフローとして自分で組む形になる（Render/RailwayのようなGUI上のネイティブ自動デプロイは無い） |
| DB | Fly Postgres（自前運用のマネージドPostgresクラスタ）を提供。無料枠は無く、Machine同様に従量課金 |
| 備考 | エッジロケーションでのグローバル分散配置に強みがあるが、2025年にかけて信頼性に関する指摘も見られる。小規模なTodoアプリ用途では機能過多になりやすい |

### 3.4 比較まとめ

| 観点 | Render | Railway | Fly.io |
|---|---|---|---|
| 無料での常時稼働 | 不可（15分アイドルでスリープ） | 不可（トライアルクレジット消費のみ） | 不可（無料枠自体が廃止） |
| 最安の常時稼働コスト目安 | $7/月（Starter） | 実質$5/月（Hobbyの月額込みクレジット） | 約$2〜/月（最小構成、従量課金） |
| セットアップの手間 | 低い（GUI＋render.yamlのIaC） | 非常に低い（GUI中心、DB連携が自動） | 中〜高い（CLI・TOML設定が前提） |
| CI/CD | pushトリガー自動デプロイをネイティブ搭載 | pushトリガー自動デプロイをネイティブ搭載 | GitHub Actions側で`flyctl deploy`を自前で組む |
| 学習コスト | 低い | 低い | やや高い（リージョン・ボリューム等の概念を理解する必要） |

- **コスト**：小規模なTodoアプリ用途であれば、RailwayのHobbyプラン（$5/月）が常時稼働・従量課金で予測しやすい。Fly.ioは最小構成なら$2/月程度からと理論上は最安だが、無料枠が無く従量課金の見積もりに慣れが必要。Renderは無料枠があるが、スリープ・コールドスタートがあるため常時稼働を求めるならStarter以上（$7/月〜）が必要。
- **難易度**：Render・RailwayはDockerfileを検出して自動ビルドする仕組みがあり学習コストが低い。RailwayはDB連携の環境変数注入が特に簡単。RenderはIaC（render.yaml）による再現性に優れる。Fly.ioはCLI操作とTOML設定への理解が前提となり、学習コースの初期段階（本プロジェクトの想定学習者）にはやや不向き。
- **CI/CD**：Render・RailwayはGitHub pushトリガーの自動デプロイをネイティブサポートしており、GitHub Actionsは「テスト→ビルド」までに留めることができる。Fly.ioは`flyctl deploy`をGitHub Actionsワークフロー内で明示的に呼び出す必要があり、CI/CD構築の自由度は高い反面、初期設定の手間が増える。

---

## 4. CI/CD連携の設計案

GitHub Actionsで以下のようなワークフローを組み、テストとlintを通過したコードのみが自動デプロイされる構成が望ましい。

```yaml
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
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run pytest
```

- `main`ブランチへのpushがテストを通過した後、Render/RailwayのGitHub連携が自動的に検知してデプロイを実行する構成であれば、GitHub Actions側にデプロイ処理を持たせる必要がない。
- より厳密に「テスト成功後のみデプロイ」を保証したい場合は、Render/Railwayの自動デプロイをオフにし、GitHub ActionsからRender/Railwayの Deploy Hook（Webhook URL）やCLI（`railway up`）を呼び出す方式もある。

---

## 5. 推奨構成

**コンテナ化：マルチステージDockerfile（uv採用）／デプロイ先：Railway（Hobbyプラン, $5/月）を第一候補、Render（Starter, $7/月〜）を次点とする。Fly.ioは今回は非推奨。**

### 推奨理由

1. **コンテナ化はマルチステージ＋uvで確定**：ビルドステージで`uv sync --frozen`により依存関係を再現性高くインストールし、実行ステージには`.venv`とソースのみをコピーする構成（2.2節）はイメージサイズ・ビルド速度・再現性の全てで有利であり、ローカル・CI・本番で同一Dockerfileを使い回せる。非root実行とHEALTHCHECKも本番運用の基本要件として採用する。
2. **デプロイ先はRailwayを第一候補とする**：
   - 本プロジェクトは学習用の小規模Todoアプリであり、コストは低く予測可能であることが望ましい。RailwayのHobbyプラン（$5/月固定＋使用量に応じたクレジット消化）は、Render無料枠のようなコールドスタート（30〜60秒）が無く、常時稼働のWebアプリとして体験が安定する。
   - DB（PostgreSQL等）を追加する際もワンクリックでプロビジョニングでき、環境変数が自動連携されるため、データベース設計担当との統合がスムーズ。
   - Dockerfileを検出した自動ビルド・GitHub pushトリガーの自動デプロイがネイティブにあり、GitHub Actions側は「テスト＋lint」に専念できる（4節）。
3. **Renderは次点**：無料枠でまず動作確認をしたい・複数環境（staging/production）をIaC（render.yaml）で厳密に管理したい場合に適する。ただし無料枠はスリープするため、学習過程で「常時アクセスできるデモURL」を維持したいなら最初からStarter（$7/月）を検討する。
4. **Fly.ioは今回は非推奨**：2024年に恒常無料枠が廃止され、CLI・TOMLベースの設定（リージョン、ボリューム等）を理解する必要があるため、学習コストに対してこの規模のアプリにはオーバースペック。将来的にグローバル分散配置やエッジ配信が必要になった場合の選択肢として留めておく。
5. **CI/CD**：GitHub ActionsでPRごとに`uv run pytest`を実行し（4節のワークフロー例）、mainブランチへのマージ後はRailway/Renderのpushトリガー自動デプロイを利用する。テスト成功を厳密にデプロイの条件としたい場合は、自動デプロイをオフにしてGitHub ActionsからDeploy Hook／CLIを呼び出す方式に切り替える。

---

### Sources
- [Pricing | Render](https://render.com/pricing)
- [Platforms with a real free tier for developers in 2026](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)
- [Render vs Railway 2026 - Pricing, DX & When to Use Each – Encore](https://encore.dev/articles/render-vs-railway)
- [Pricing Plans | Railway Docs](https://docs.railway.com/pricing/plans)
- [Pricing | Railway](https://railway.com/pricing)
- [Railway vs Render: which platform fits your workload in 2026? | Northflank](https://northflank.com/blog/railway-vs-render)
- [Pricing · Fly](https://fly.io/pricing/)
- [Fly.io Resource Pricing · Fly Docs](https://fly.io/docs/about/pricing/)
- [7 Fly.io Alternatives in 2026: Real Pricing After the Free Tier Died - ExpressTech](https://expresstech.io/7-fly-io-alternatives-in-2026-real-pricing-after-the-free-tier-died/)
- [Fly.io Free Tier 2026: What's Left After the Cuts? - SaaSPricePulse](https://www.saaspricepulse.com/tools/flyio)
- [FastAPI in Containers - Docker - FastAPI](https://fastapi.tiangolo.com/deployment/docker/)
- [Using uv with FastAPI | uv](https://docs.astral.sh/uv/guides/integration/fastapi/)
- [Docker in Practice #1: Containerizing FastAPI — uv, Multi-stage, non-root](https://schoolofweb.net/en/posts/docker-practice-1/)
- [FastAPI Docker Best Practices | Better Stack Community](https://betterstack.com/community/guides/scaling-python/fastapi-docker-best-practices/)
