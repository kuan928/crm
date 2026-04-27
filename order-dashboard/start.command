#!/bin/bash
# 訂單分析儀表板 — Mac 一鍵啟動
#
# 用法:在 Finder 中雙擊本檔案即可。
# 第一次啟動會自動建立 Python 虛擬環境並安裝相依套件,約需 1-2 分鐘。
# 之後每次啟動都很快,大約 3 秒。
#
# 需求:Mac 上需先安裝 Python 3.10 或更新版本(僅需安裝一次)。
# 若沒有,本腳本會引導你前往下載。

# 切到腳本所在目錄,讓資料夾可以放任何位置
cd "$(dirname "$0")" || exit 1

# 視窗收尾處理:不論成功或失敗都暫停,讓使用者看到訊息
finish() {
    rc=$?
    echo
    if [ "$rc" -ne 0 ] && [ "$rc" -ne 130 ]; then
        echo "❌ 啟動失敗(exit code: $rc)"
        echo "   請把上方訊息截圖傳給開發者協助除錯。"
    else
        echo "✓ 已關閉儀表板。"
    fi
    echo
    echo "(按任意鍵關閉此視窗)"
    read -n 1 -s
}
trap finish EXIT

clear
echo "============================================="
echo "         訂單分析儀表板  Mac 啟動程式"
echo "============================================="
echo

# 1. 找一個可用的 Python 3.10+
find_python() {
    for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$cmd" >/dev/null 2>&1; then
            v=$("$cmd" -c "import sys; print(sys.version_info.major*100+sys.version_info.minor)" 2>/dev/null) || continue
            if [ -n "$v" ] && [ "$v" -ge 310 ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON=$(find_python)
if [ -z "$PYTHON" ]; then
    echo "❌ 找不到 Python 3.10 或更新的版本。"
    echo
    echo "請先安裝 Python(只需要做一次):"
    echo
    echo "   方法 A(最簡單):前往 https://www.python.org/downloads/"
    echo "                  下載最新版的 macOS 安裝檔,雙擊安裝。"
    echo
    echo "   方法 B(若你會用 Homebrew):"
    echo "                  brew install python@3.12"
    echo
    echo "安裝完成後再雙擊本檔案即可。"
    exit 1
fi

PYVER=$("$PYTHON" --version 2>&1)
echo "✓ 找到 Python: $PYVER"
echo

# 2. 建立虛擬環境
if [ ! -d ".venv" ]; then
    echo "⏳ 第一次啟動,建立 Python 虛擬環境(約 10 秒)..."
    "$PYTHON" -m venv .venv || {
        echo "❌ 無法建立虛擬環境。"
        echo "   你的 Python 可能缺少 venv 模組,試試看用 python.org 官方版重裝。"
        exit 1
    }
    echo "✓ 虛擬環境建立完成"
    echo
fi

# 3. 啟用 venv
# shellcheck disable=SC1091
source .venv/bin/activate

# 4. 安裝套件(只在 requirements.txt 變新時才重裝)
SENTINEL=".venv/.installed"
if [ ! -f "$SENTINEL" ] || [ "requirements.txt" -nt "$SENTINEL" ]; then
    echo "⏳ 安裝相依套件(第一次約 1-2 分鐘,後續啟動會跳過此步驟)..."
    python -m pip install --upgrade pip --quiet 2>&1 | grep -v "^WARNING" || true
    python -m pip install -r requirements.txt --quiet 2>&1 | grep -v "^WARNING" || true
    if [ $? -ne 0 ]; then
        echo "❌ 套件安裝失敗。請檢查網路連線後再試。"
        exit 1
    fi
    touch "$SENTINEL"
    echo "✓ 套件安裝完成"
    echo
fi

# 5. 啟動 Streamlit
echo "🚀 正在啟動儀表板..."
echo "   瀏覽器會自動打開,網址是 http://localhost:8501"
echo
echo "   📌 要關閉儀表板:回到此終端機視窗,按 Control + C"
echo "      或直接關閉這個視窗(Streamlit 會跟著結束)"
echo
echo "---------------------------------------------"

exec streamlit run app.py --browser.gatherUsageStats=false
