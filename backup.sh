#!/bin/bash

# ===============================================
# Smart Eval - 备份脚本
# ===============================================

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Smart Eval - 备份脚本${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""

# 创建备份目录
BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"

# 生成备份文件名
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/smart-eval-backup-$TIMESTAMP.tar.gz"

echo "创建备份..."
echo "备份目录:"
echo "  - data/    (数据库)"
echo "  - tmp/     (数据集和报告)"
echo "  - logs/    (日志)"
echo ""

# 创建备份
BACKUP_ITEMS=()
for item in data tmp logs; do
    if [ -e "$item" ]; then
        BACKUP_ITEMS+=("$item")
    fi
done
if [ ${#BACKUP_ITEMS[@]} -eq 0 ]; then
    mkdir -p data
    BACKUP_ITEMS+=("data")
fi
tar -czf "$BACKUP_FILE" "${BACKUP_ITEMS[@]}"
chmod 600 "$BACKUP_FILE"

# 检查备份大小
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

echo -e "${GREEN}✓ 备份完成！${NC}"
echo ""
echo "备份文件: $BACKUP_FILE"
echo "备份大小: $BACKUP_SIZE"
echo ""

# 清理旧备份（保留最近 7 个）
echo "清理旧备份（保留最近 7 个）..."
cd "$BACKUP_DIR"
ls -t smart-eval-backup-*.tar.gz 2>/dev/null | tail -n +8 | xargs -r rm -f
cd ..

echo -e "${GREEN}✓ 清理完成${NC}"
echo ""
echo "恢复备份命令:"
echo "  tar -xzf $BACKUP_FILE"
