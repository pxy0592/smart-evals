import React from 'react';
import { DeleteOutlined } from '@ant-design/icons';
import { Button, Space } from 'antd';

interface BatchActionBarProps {
    selectedCount: number;
    onDelete: () => void;
    onCancel: () => void;
    deleting?: boolean;
    itemName?: string;
}

export const BatchActionBar: React.FC<BatchActionBarProps> = ({
    selectedCount,
    onDelete,
    onCancel,
    deleting = false,
    itemName = '项',
}) => {
    if (selectedCount === 0) return null;

    return (
        <div className="batch-action-bar" role="status">
            <span className="batch-action-bar__copy">
                已选择 {selectedCount} 个{itemName}
            </span>
            <Space>
                <Button onClick={onCancel}>取消选择</Button>
                <Button
                    danger
                    type="primary"
                    icon={<DeleteOutlined />}
                    loading={deleting}
                    onClick={onDelete}
                >
                    批量删除
                </Button>
            </Space>
        </div>
    );
};
