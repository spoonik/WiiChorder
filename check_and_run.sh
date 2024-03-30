#!/bin/bash

# ファイルのパス
FILE=/home/pi/Public/.running

# ファイルが存在し、かつ1分以上前に更新されているかチェック
if [ -f "$FILE" ]; then
    if [ "$(( $(date +%s) - $(stat -c %Y "$FILE") ))" -gt 60 ]; then
        # 条件を満たす場合、Pythonスクリプトを実行
        python /home/pi/Public/WiiChorder.py
    fi
else
    # ファイルが存在しない場合、Pythonスクリプトを実行
    python /home/pi/Public/WiiChorder.py
fi
