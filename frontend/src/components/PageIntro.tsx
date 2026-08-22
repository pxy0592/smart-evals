import React from 'react';
import { Typography } from 'antd';

const { Title, Text } = Typography;

interface PageIntroProps {
    title: string;
    description: string;
    actions?: React.ReactNode;
}

export const PageIntro: React.FC<PageIntroProps> = ({
    title,
    description,
    actions,
}) => (
    <div className="page-intro">
        <div className="page-intro__copy">
            <Title level={2}>{title}</Title>
            <Text type="secondary">{description}</Text>
        </div>
        {actions && <div className="page-intro__actions">{actions}</div>}
    </div>
);
