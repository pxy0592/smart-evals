import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Form, Input, Select, Space, message } from 'antd';
import { ReloadOutlined, RocketOutlined } from '@ant-design/icons';
import {
    datasetApi,
    metricApi,
    ragConnectionApi,
    ragResourceApi,
    taskApi,
} from '../services/evaluation';
import type {
    AssistantRef,
    Dataset,
    Metric,
    RagConnectionSummary,
    RagResourceRef,
} from '../services/evaluation';

interface EvaluationTaskFormProps {
    initialDatasetId?: string;
    onCreated?: () => void;
    onCancel?: () => void;
}

export const EvaluationTaskForm: React.FC<EvaluationTaskFormProps> = ({
    initialDatasetId,
    onCreated,
    onCancel,
}) => {
    const [form] = Form.useForm();
    const [connections, setConnections] = useState<RagConnectionSummary[]>([]);
    const [assistants, setAssistants] = useState<AssistantRef[]>([]);
    const [knowledgeBases, setKnowledgeBases] = useState<RagResourceRef[]>([]);
    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [metrics, setMetrics] = useState<Metric[]>([]);
    const [mode, setMode] = useState<AssistantRef['knowledge_base_selection_mode']>(null);
    const [loading, setLoading] = useState(false);
    const connectionId = Form.useWatch('connection_id', form);

    const selectedConnection = useMemo(
        () => connections.find((item) => item.id === connectionId),
        [connections, connectionId],
    );

    const loadBase = async () => {
        setLoading(true);
        try {
            const [connectionResult, datasetResult, metricResult] = await Promise.all([
                ragConnectionApi.list(),
                datasetApi.list({ limit: 100 }),
                metricApi.list(),
            ]);
            const available = connectionResult.connections.filter((item) => item.enabled);
            setConnections(available);
            setDatasets(datasetResult.datasets.filter((item) => item.status === 'completed'));
            setMetrics(metricResult.metrics || []);
            const defaultId = available[0]?.id;
            form.setFieldsValue({ connection_id: defaultId, dataset_id: initialDatasetId, batch_size: 10 });
            if (defaultId) await loadAssistants(defaultId);
        } catch {
            message.error('加载评测任务选项失败');
        } finally {
            setLoading(false);
        }
    };

    const loadAssistants = async (id: string) => {
        form.setFieldsValue({ assistant_id: undefined, knowledge_base_ids: [] });
        setMode(null);
        setKnowledgeBases([]);
        const result = await ragResourceApi.listAssistants(id, { limit: 100 });
        setAssistants(result.items);
    };

    const selectAssistant = async (assistantId: string) => {
        const assistant = assistants.find((item) => item.id === assistantId);
        const nextMode = assistant?.knowledge_base_selection_mode || null;
        setMode(nextMode);
        form.setFieldValue('knowledge_base_ids', []);
        if (nextMode === 'selected' && connectionId) {
            const result = await ragResourceApi.listKnowledgeBases(connectionId, {
                assistant_id: assistantId,
                limit: 100,
            });
            setKnowledgeBases(result.items.filter((item) => item.selectable));
        } else {
            setKnowledgeBases([]);
        }
    };

    useEffect(() => {
        void loadBase();
    }, []);

    const submit = async () => {
        const values = await form.validateFields();
        const assistant = assistants.find((item) => item.id === values.assistant_id);
        if (!assistant?.knowledge_base_selection_mode) {
            return message.error('Agent 知识库模式未知，请刷新');
        }
        setLoading(true);
        try {
            await taskApi.create({
                name: values.name,
                dataset_id: values.dataset_id,
                metrics: values.metrics,
                batch_size: values.batch_size,
                rag_target: {
                    provider: selectedConnection!.provider,
                    connection_id: values.connection_id,
                    assistant_id: values.assistant_id,
                    knowledge_base_ids:
                        assistant.knowledge_base_selection_mode === 'selected'
                            ? values.knowledge_base_ids
                            : [],
                },
            });
            message.success('评测任务创建成功');
            form.resetFields();
            onCreated?.();
        } catch {
            message.error('创建评测任务失败');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Form form={form} layout="vertical" disabled={loading}>
            <Form.Item label="任务名称" name="name"><Input placeholder="例如：IntelliQ 回归评测" /></Form.Item>
            <Form.Item label="RAG 系统" name="connection_id" rules={[{ required: true }]}>
                <Select onChange={(value) => void loadAssistants(value)} options={connections.map((item) => ({ value: item.id, label: `${item.name} (${item.provider})` }))} />
            </Form.Item>
            <Form.Item label="对话助手 / Agent" name="assistant_id" rules={[{ required: true }]}>
                <Select onChange={(value) => void selectAssistant(value)} options={assistants.map((item) => ({ value: item.id, label: item.name, disabled: !item.selectable }))} />
            </Form.Item>
            {mode === 'selected' && (
                <Form.Item label="知识库" name="knowledge_base_ids" rules={[{ required: true, type: 'array', min: 1, message: 'selected 模式至少选择一个知识库' }]}>
                    <Select mode="multiple" options={knowledgeBases.map((item) => ({ value: item.id, label: item.name }))} />
                </Form.Item>
            )}
            {mode && mode !== 'selected' && <Alert type="info" showIcon message={mode === 'all' ? '该 Agent 使用全部可用知识范围，无需手动选择知识库。' : '该 Agent 不使用知识库。'} style={{ marginBottom: 16 }} />}
            <Form.Item label="评测数据集" name="dataset_id" rules={[{ required: true }]}>
                <Select options={datasets.map((item) => ({ value: item.id, label: `${item.name} (${item.num_samples} 样本)` }))} />
            </Form.Item>
            <Form.Item label="评测指标" name="metrics" rules={[{ required: true, type: 'array', min: 1 }]}>
                <Select mode="multiple" options={metrics.map((item) => ({ value: item.name, label: item.display_name }))} />
            </Form.Item>
            <Form.Item label="批处理大小" name="batch_size"><Select options={[5, 10, 20].map((value) => ({ value, label: value }))} /></Form.Item>
            <Space>
                <Button type="primary" icon={<RocketOutlined />} loading={loading} onClick={submit}>创建任务</Button>
                <Button icon={<ReloadOutlined />} onClick={loadBase}>刷新</Button>
                {onCancel && <Button onClick={onCancel}>取消</Button>}
            </Space>
        </Form>
    );
};
