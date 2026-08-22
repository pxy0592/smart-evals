import React, { useEffect, useState } from 'react';
import { Alert, Button, Card, Form, Input, Space, Switch, Tag, Typography, message } from 'antd';
import { ApiOutlined, ReloadOutlined, SaveOutlined } from '@ant-design/icons';
import { ragConnectionApi } from '../services/evaluation';
import type { RagConnectionSummary } from '../services/evaluation';

const { Text } = Typography;

export const RagConnectionForm: React.FC = () => {
    const [form] = Form.useForm();
    const [connection, setConnection] = useState<RagConnectionSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(false);

    const load = async () => {
        setLoading(true);
        try {
            const result = await ragConnectionApi.list();
            const current = result.connections.find((item) => item.provider === 'intelliq') || null;
            setConnection(current);
            form.setFieldsValue({
                name: current?.name || 'IntelliQ',
                api_url: current?.api_url || 'https://ai-intelliq.peraglobal.com',
                enabled: current?.enabled ?? true,
                api_key: '',
                admin_token: sessionStorage.getItem('smart_eval_admin_token') || '',
            });
        } catch {
            message.error('获取 RAG 系统配置失败');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void load();
    }, []);

    const token = () => {
        const value = String(form.getFieldValue('admin_token') || '').trim();
        if (!value) throw new Error('请输入部署级管理员令牌');
        sessionStorage.setItem('smart_eval_admin_token', value);
        return value;
    };

    const save = async () => {
        const values = await form.validateFields();
        setSaving(true);
        try {
            const data: any = { name: values.name, api_url: values.api_url, enabled: values.enabled };
            if (values.api_key) data.api_key = values.api_key;
            const saved = connection
                ? await ragConnectionApi.update(connection.id, data, token())
                : await ragConnectionApi.create({ provider: 'intelliq', ...data, api_key: values.api_key }, token());
            setConnection(saved);
            form.setFieldValue('api_key', '');
            message.success('IntelliQ 连接配置已保存');
        } catch (error: any) {
            message.error(error?.message || '保存连接失败');
        } finally {
            setSaving(false);
        }
    };

    const test = async () => {
        if (!connection) return message.warning('请先保存连接');
        setTesting(true);
        try {
            const result = await ragConnectionApi.test(connection.id, token());
            message.success(`连接可用：${result.knowledge_base_count} 个知识库，${result.assistant_count} 个 Agent`);
            await load();
        } catch {
            message.error('连接测试失败');
        } finally {
            setTesting(false);
        }
    };

    return (
        <Card loading={loading} title="IntelliQ 连接" extra={connection && <Tag color={connection.status === 'available' ? 'success' : connection.status === 'unavailable' ? 'error' : 'default'}>{connection.status}</Tag>}>
            <Alert type="info" showIcon message="API URL 可填写服务根地址或以 /api/v1 结尾的地址。API Key 保存后不会再次返回页面。" style={{ marginBottom: 20 }} />
            <Form form={form} layout="vertical">
                <Form.Item label="连接名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
                <Form.Item label="API URL" name="api_url" rules={[{ required: true, type: 'url' }]}><Input placeholder="https://ai-intelliq.peraglobal.com" /></Form.Item>
                <Form.Item label={connection?.api_key_configured ? '替换 API Key（留空保持不变）' : 'API Key'} name="api_key" rules={[{ required: !connection }]}><Input.Password autoComplete="new-password" /></Form.Item>
                <Form.Item label="部署级管理员令牌" name="admin_token" rules={[{ required: true }]}><Input.Password autoComplete="off" /></Form.Item>
                <Form.Item label="启用连接" name="enabled" valuePropName="checked"><Switch /></Form.Item>
                <Space>
                    <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save}>保存</Button>
                    <Button icon={<ApiOutlined />} loading={testing} disabled={!connection} onClick={test}>测试连接</Button>
                    <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
                </Space>
                {connection?.error && <Text type="danger" style={{ display: 'block', marginTop: 16 }}>{connection.error.message}</Text>}
            </Form>
        </Card>
    );
};
