#!/usr/bin/env bash
# Bootstrap the yantu project: create runtime dirs and seed files.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Creating runtime directories..."
mkdir -p data
mkdir -p data/chroma
mkdir -p models

if [ ! -f .env ]; then
  echo "==> .env not found, copying from .env.example"
  cp .env.example .env
  echo "    ⚠️  请编辑 .env 填入 LLM_API_KEY"
fi

if [ ! -f seed/user_profile.json ]; then
  echo "==> seed/user_profile.json not found, copying default"
  mkdir -p seed
  cp seed/user_profile.default.json seed/user_profile.json 2>/dev/null || true
fi

echo "==> Done. Next steps:"
echo "    1. 编辑 .env 填入 LLM_API_KEY"
echo "    2. python -m scripts.ingest_seed   # 摄入个人调研资料"
echo "    3. chainlit run src/yantu/ui/app.py"
