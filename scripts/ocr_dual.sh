#!/bin/bash
# OCR 双引擎处理脚本
# 用法: bash ~/.openclaw/workspace/scripts/ocr_dual.sh <图片路径>
# 功能: 同时运行 RapidOCR 和 macOS Vision OCR，自动选择更优结果输出

IMAGE_PATH="$1"

if [ -z "$IMAGE_PATH" ]; then
  echo "错误: 请提供图片路径"
  echo "用法: bash $0 <图片路径>"
  exit 1
fi

if [ ! -f "$IMAGE_PATH" ]; then
  echo "错误: 文件不存在 - $IMAGE_PATH"
  exit 1
fi

# 临时文件
RAPID_FILE="/tmp/kb_processing/ocr/rapid_result.txt"
VISION_FILE="/tmp/kb_processing/ocr/vision_result.txt"

# 清空临时文件
> "$RAPID_FILE"
> "$VISION_FILE"

# ===== 引擎 1: RapidOCR =====
(source ~/Desktop/rapidocr_venv/bin/activate && cd ~/.openclaw/workspace/skills/RapidOCR/python && python3 -c "
from rapidocr import RapidOCR
engine = RapidOCR()
result = engine('$IMAGE_PATH')
if result.txts:
  print('\n'.join(result.txts))
" > "$RAPID_FILE" 2>/dev/null) &
PID_RAPID=$!

# ===== 引擎 2: macOS Vision OCR =====
(~/.openclaw/workspace/skills/macos-vision-ocr/.build/release/macos-vision-ocr --img "$IMAGE_PATH" > "$VISION_FILE" 2>/dev/null) &
PID_VISION=$!

# 等待两个引擎都完成（最长等待60秒）
wait $PID_RAPID 2>/dev/null
wait $PID_VISION 2>/dev/null

# ===== 比较并选择最优结果 =====
python3 << 'PYEOF'
def quality_score(text):
  if not text.strip():
    return 0
  score = 0
  score += len(text.strip())
  score += text.count('\n') * 5
  garbled = sum(1 for c in text if ord(c) > 0xFFFF or c in '□■◆◇○●△▽')
  score -= garbled * 50
  consecutive_spaces = text.count('  ')
  score -= consecutive_spaces * 10
  return score

with open('/tmp/kb_processing/ocr/rapid_result.txt', 'r') as f:
  rapid = f.read()
with open('/tmp/kb_processing/ocr/vision_result.txt', 'r') as f:
  vision = f.read()

rapid_score = quality_score(rapid)
vision_score = quality_score(vision)

if rapid_score == 0 and vision_score == 0:
  print("[OCR_ERROR] 两个引擎均未识别到文字")
elif rapid_score >= vision_score:
  print(rapid.strip())
else:
  print(vision.strip())
PYEOF
