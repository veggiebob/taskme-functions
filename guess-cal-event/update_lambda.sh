#!/usr/bin/env bash

# Template generated using GPT-4

set -euo pipefail

# ─── CONFIG ────────────────────────────────────────────────────────────────
VENV_DIR=".venv"                        # path to your virtualenv
REQ_FILE="requirements.txt"             # where to freeze deps
PACKAGE_DIR="lambda-package"            # temp install dir
DEPLOY_ZIP="serialize-prompt.zip"       # output zip
SRC_GLOB="env.json *.py"                # which files to include from CWD
FUNCTION_NAME="guessCalendarEvent"      # AWS Lambda function name
# ──────────────────────────────────────────────────────────────────────────

echo "📦 Freezing dependencies from ${VENV_DIR} → ${REQ_FILE}"
# 1. freeze deps
source "${VENV_DIR}/bin/activate"
pip freeze > "${REQ_FILE}"
deactivate

echo "🗂️ Preparing clean package dir: ${PACKAGE_DIR}/"
rm -rf "${PACKAGE_DIR}"
mkdir -p "${PACKAGE_DIR}"

echo "📥 Installing dependencies into ${PACKAGE_DIR}/"
pip install --upgrade -r "${REQ_FILE}" -t "${PACKAGE_DIR}/"

echo "📄 Copying source files into ${PACKAGE_DIR}/"
cp ${SRC_GLOB} "${PACKAGE_DIR}/"

echo "🦅 Creating ${DEPLOY_ZIP}"
pushd "${PACKAGE_DIR}" > /dev/null
zip -r "../${DEPLOY_ZIP}" . > /dev/null
popd > /dev/null

echo "📤 Uploading ${DEPLOY_ZIP} to AWS Lambda"
aws lambda update-function-code --function-name "${FUNCTION_NAME}" --zip-file fileb://"${DEPLOY_ZIP}"
if [ $? -ne 0 ]; then
    echo "❌ Error uploading to Lambda. Please check your AWS credentials and function name."
    exit 1
fi

echo "✅ Done! Upload ${DEPLOY_ZIP} to Lambda."