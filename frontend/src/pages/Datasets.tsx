import React, { useState, useEffect, useRef } from 'react';
import {
    Card,
    Table,
    Button,
    Space,
    Tag,
    Modal,
    Upload,
    message,
    Typography,
    Dropdown,
    Input,
    Form,
    Select,
    Tabs,
    Descriptions,
    List,
    Empty,
    Statistic,
    Spin,
    InputNumber,
    App,
    Alert,
    Skeleton,
} from 'antd';
import {
    UploadOutlined,
    FileTextOutlined,
    DatabaseOutlined,
    DownloadOutlined,
    DeleteOutlined,
    EyeOutlined,
    PlusOutlined,
    SearchOutlined,
    FileExcelOutlined,
    FileMarkdownOutlined,
    RobotOutlined,
    ReloadOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
    datasetApi,
    ragConnectionApi,
    ragResourceApi,
} from '../services/evaluation';
import type {
    Dataset as ApiDataset,
    RagConnectionSummary,
    RagResourceRef,
} from '../services/evaluation';
import { useBatchDelete } from '../hooks/useBatchDelete';
import { BatchActionBar } from '../components/BatchActionBar';
import { PageIntro } from '../components/PageIntro';
import { EvaluationTaskForm } from '../components/EvaluationTaskForm';

const { Title, Text, Paragraph } = Typography;
const { Search } = Input;
const { Dragger } = Upload;

interface DatasetSample {
    question: string;
    expected_answer?: string;
    contexts?: string[];
}

const Datasets: React.FC = () => {
    const [datasets, setDatasets] = useState<ApiDataset[]>([]);
    const [loading, setLoading] = useState(true);
    const [uploadVisible, setUploadVisible] = useState(false);
    const [previewVisible, setPreviewVisible] = useState(false);
    const [generateVisible, setGenerateVisible] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [createTaskVisible, setCreateTaskVisible] = useState(false);
    const [selectedDataset, setSelectedDataset] = useState<ApiDataset | null>(
        null,
    );
    const [datasetSamples, setDatasetSamples] = useState<DatasetSample[]>([]);
    const [samplesLoading, setSamplesLoading] = useState(false);
    const [searchText, setSearchText] = useState('');
    // AI generation session state (on-demand)
    const [genConnections, setGenConnections] = useState<RagConnectionSummary[]>([]);
    const [genConnectionLoading, setGenConnectionLoading] = useState(false);
    const [genConnectionError, setGenConnectionError] = useState<string | null>(null);
    const [genSelectedConnectionId, setGenSelectedConnectionId] = useState<string | null>(null);
    const [genKbs, setGenKbs] = useState<RagResourceRef[]>([]);
    const [genKbLoading, setGenKbLoading] = useState(false);
    const genAbortRef = useRef<AbortController | null>(null);
    const [form] = Form.useForm();
    const [generateForm] = Form.useForm();
    const [createTaskForm] = Form.useForm();
    const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const appContext = App.useApp();

    useEffect(() => {
        fetchDatasets();

        return () => {
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
            }
        };
    }, []);

    useEffect(() => {
        const hasProcessing = datasets.some(
            (ds) => ds.status === 'processing' || ds.status === 'pending',
        );

        if (hasProcessing && !pollingIntervalRef.current) {
            pollingIntervalRef.current = setInterval(async () => {
                try {
                    const response = await datasetApi.list({ limit: 100 });
                    setDatasets(response.datasets || []);
                } catch (error) {
                    console.error('Failed to fetch datasets:', error);
                }
            }, 3000);
        } else if (!hasProcessing && pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
        }
    }, [datasets.map((d) => d.status).join(',')]);

    const fetchDatasets = async () => {
        setLoading(true);
        try {
            const response = await datasetApi.list({ limit: 100 });
            setDatasets(response.datasets || []);
        } catch (error) {
            console.error('Failed to fetch datasets:', error);
            message.error('获取数据集列表失败');
        } finally {
            setLoading(false);
        }
    };

    // 使用统一的批量删除 Hook
    const {
        rowSelection,
        batchDeleting,
        handleBatchDelete,
        clearSelection,
        selectedRowKeys,
    } = useBatchDelete({
        apiCall: datasetApi.batchDelete,
        itemName: '数据集',
        onSuccess: fetchDatasets,
        permanentWarning: true,
    });

    const columns: ColumnsType<ApiDataset> = [
        {
            title: '数据集名称',
            dataIndex: 'name',
            key: 'name',
            render: (text, record) => (
                <Space>
                    {record.file_type === 'csv' && <FileExcelOutlined />}
                    {record.file_type === 'json' && <FileTextOutlined />}
                    {record.file_type === 'md' && <FileMarkdownOutlined />}
                    <a onClick={() => handlePreview(record)}>{text}</a>
                </Space>
            ),
        },
        {
            title: '描述',
            dataIndex: 'description',
            key: 'description',
            ellipsis: true,
        },
        {
            title: '样本数',
            dataIndex: 'num_samples',
            key: 'num_samples',
            sorter: (a, b) => a.num_samples - b.num_samples,
        },
        {
            title: '状态',
            key: 'status',
            render: (_, record) => {
                const statusMap: Record<
                    string,
                    { color: string; text: string; icon?: React.ReactNode }
                > = {
                    pending: { color: 'default', text: '待处理' },
                    processing: { color: 'processing', text: '处理中' },
                    completed: { color: 'success', text: '已完成' },
                    failed: { color: 'error', text: '失败' },
                };
                const status = statusMap[record.status] || statusMap.pending;
                return (
                    <Space>
                        <Tag color={status.color}>{status.text}</Tag>
                        {record.status === 'processing' &&
                            record.progress !== undefined && (
                                <span style={{ fontSize: 12, color: '#666' }}>
                                    {record.progress}%
                                </span>
                            )}
                    </Space>
                );
            },
        },
        {
            title: '数据完整性',
            key: 'completeness',
            render: (_, record) => {
                const hasReference = Boolean(record.has_reference);
                const hasContexts = Boolean(record.has_contexts);

                return (
                    <Space>
                        {hasReference && <Tag color="green">包含参考答案</Tag>}
                        {hasContexts && <Tag color="blue">包含上下文</Tag>}
                        {!hasReference && !hasContexts && <Tag>仅问题</Tag>}
                    </Space>
                );
            },
        },
        {
            title: '创建时间',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (text) =>
                text ? new Date(text).toLocaleString('zh-CN') : '-',
            sorter: (a, b) =>
                new Date(a.created_at).getTime() -
                new Date(b.created_at).getTime(),
        },
        {
            title: '操作',
            key: 'action',
            render: (_, record) => (
                <Space size="middle">
                    <Button
                        size="small"
                        icon={<EyeOutlined />}
                        onClick={() => handlePreview(record)}
                    >
                        预览
                    </Button>
                    <Button
                        size="small"
                        type="primary"
                        onClick={() => handleCreateTask(record)}
                    >
                        创建评测
                    </Button>
                    <Button
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => handleDelete(record)}
                    >
                        删除
                    </Button>
                </Space>
            ),
        },
    ];

    const handlePreview = async (dataset: ApiDataset) => {
        setSelectedDataset(dataset);
        setPreviewVisible(true);
        setSamplesLoading(true);
        try {
            const response = await datasetApi.getSamples(dataset.id, {
                limit: 10,
            });
            setDatasetSamples(response.samples || []);
        } catch (error) {
            console.error('Failed to fetch dataset samples:', error);
            message.error('获取数据集样本失败');
        } finally {
            setSamplesLoading(false);
        }
    };

    const handleCreateTask = (dataset: ApiDataset) => {
        setSelectedDataset(dataset);
        setCreateTaskVisible(true);
    };

    const handleDelete = async (dataset: ApiDataset) => {
        if (appContext.modal) {
            appContext.modal.confirm({
                title: '确认删除',
                content: (
                    <div>
                        <p>
                            确定要删除数据集 <strong>"{dataset.name}"</strong>{' '}
                            吗？
                        </p>
                        <p style={{ color: '#ff4d4f', fontSize: '12px' }}>
                            此操作无法撤销。
                        </p>
                    </div>
                ),
                okText: '删除',
                okType: 'danger',
                cancelText: '取消',
                width: 400,
                onOk: async () => {
                    try {
                        await datasetApi.batchDelete([dataset.id]);
                        message.success('删除成功');
                        fetchDatasets();
                    } catch (error) {
                        console.error('Failed to delete dataset:', error);
                        message.error('删除失败');
                    }
                },
            });
        } else {
            Modal.confirm({
                title: '确认删除',
                content: (
                    <div>
                        <p>
                            确定要删除数据集 <strong>"{dataset.name}"</strong>{' '}
                            吗？
                        </p>
                        <p style={{ color: '#ff4d4f', fontSize: '12px' }}>
                            此操作无法撤销。
                        </p>
                    </div>
                ),
                okText: '删除',
                okType: 'danger',
                cancelText: '取消',
                width: 400,
                onOk: async () => {
                    try {
                        await datasetApi.batchDelete([dataset.id]);
                        message.success('删除成功');
                        fetchDatasets();
                    } catch (error) {
                        console.error('Failed to delete dataset:', error);
                        message.error('删除失败');
                    }
                },
            });
        }
    };

    const handleUpload = async (file: File) => {
        const formValues = form.getFieldsValue();

        try {
            await datasetApi.upload(file, {
                name: formValues.name || file.name,
                description: formValues.description || '',
            });
            message.success(`${file.name} 上传成功`);
            setUploadVisible(false);
            form.resetFields();
            fetchDatasets();
        } catch (error) {
            console.error('Failed to upload dataset:', error);
            message.error(`${file.name} 上传失败`);
        }

        return false;
    };

    const closeGenModal = () => {
        // Abort in-flight requests
        if (genAbortRef.current) {
            genAbortRef.current.abort();
            genAbortRef.current = null;
        }
        setGenerateVisible(false);
        generateForm.resetFields();
        setGenConnections([]);
        setGenConnectionLoading(false);
        setGenConnectionError(null);
        setGenSelectedConnectionId(null);
        setGenKbs([]);
        setGenKbLoading(false);
    };

    const loadGenConnections = async () => {
        setGenConnectionLoading(true);
        setGenConnectionError(null);
        setGenConnections([]);
        setGenSelectedConnectionId(null);
        setGenKbs([]);
        try {
            const result = await ragConnectionApi.list();
            setGenConnections(result.connections);
        } catch {
            setGenConnectionError('获取 RAG 连接列表失败');
        } finally {
            setGenConnectionLoading(false);
        }
    };

    // Load connections when AI generation modal opens
    useEffect(() => {
        if (generateVisible) {
            loadGenConnections();
        }
    }, [generateVisible]);

    const handleGenConnectionChange = async (connectionId: string) => {
        // Abort previous request
        if (genAbortRef.current) {
            genAbortRef.current.abort();
        }
        const controller = new AbortController();
        genAbortRef.current = controller;

        setGenSelectedConnectionId(connectionId);
        setGenKbs([]);
        generateForm.setFieldValue('kb_id', undefined);

        const conn = genConnections.find((c) => c.id === connectionId);
        if (!conn || !conn.capabilities.generate_dataset_from_knowledge_base) {
            return;
        }

        setGenKbLoading(true);
        try {
            const result = await ragResourceApi.listKnowledgeBases(connectionId, { limit: 100 });
            if (!controller.signal.aborted) {
                setGenKbs(result.items.filter((item) => item.selectable));
            }
        } catch {
            if (!controller.signal.aborted) {
                message.error('获取知识库列表失败');
            }
        } finally {
            if (!controller.signal.aborted) {
                setGenKbLoading(false);
            }
        }
    };

    const handleGenerateSubmit = async () => {
        try {
            const values = await generateForm.validateFields();
            setGenerating(true);

            const conn = genConnections.find((c) => c.id === genSelectedConnectionId);
            const response = await datasetApi.generateAIDataset({
                kb_id: values.kb_id,
                sample_count: values.sample_count,
                question_types: values.question_types || ['factual', 'analytical'],
                connection_id: genSelectedConnectionId!,
            });

            message.success(`AI 数据集生成成功: ${response.name}`);
            closeGenModal();
            fetchDatasets();
        } catch (error) {
            console.error('Failed to generate AI dataset:', error);
            message.error('生成 AI 数据集失败');
        } finally {
            setGenerating(false);
        }
    };

    const selectedGenConnection = genConnections.find(
        (c) => c.id === genSelectedConnectionId,
    );
    const genCapable = selectedGenConnection?.capabilities
        .generate_dataset_from_knowledge_base ?? false;

    const uploadProps: UploadProps = {
        name: 'file',
        multiple: false,
        accept: '.csv,.json,.jsonl,.xlsx,.txt',
        beforeUpload: handleUpload,
        showUploadList: false,
    };

    return (
        <div className="page-shell">
            <PageIntro
                title="数据集管理"
                description="管理评测样本、数据完整性与任务入口。"
            />

            <Card>
                <div className="page-toolbar">
                    <Space>
                        <Search
                            placeholder="搜索数据集"
                            allowClear
                            onSearch={setSearchText}
                            style={{ width: 300 }}
                        />
                        <Select defaultValue="all" style={{ width: 120 }}>
                            <Select.Option value="all">全部类型</Select.Option>
                            <Select.Option value="csv">CSV</Select.Option>
                            <Select.Option value="json">JSON</Select.Option>
                            <Select.Option value="excel">Excel</Select.Option>
                        </Select>
                    </Space>
                    <Space>
                        <Button
                            type="primary"
                            icon={<UploadOutlined />}
                            onClick={() => setUploadVisible(true)}
                        >
                            上传数据集
                        </Button>
                        <Button
                            icon={<RobotOutlined />}
                            onClick={() => setGenerateVisible(true)}
                        >
                            AI 智能生成数据集
                        </Button>
                    </Space>
                </div>

                <BatchActionBar
                    selectedCount={selectedRowKeys.length}
                    onDelete={handleBatchDelete}
                    onCancel={clearSelection}
                    deleting={batchDeleting}
                    itemName="数据集"
                />

                <Table
                    columns={columns}
                    dataSource={datasets}
                    loading={loading}
                    rowKey="id"
                    rowSelection={rowSelection}
                    pagination={{
                        pageSize: 10,
                        showSizeChanger: true,
                        showQuickJumper: true,
                        showTotal: (total) => `共 ${total} 个数据集`,
                    }}
                    locale={{ emptyText: '暂无数据集' }}
                />
            </Card>

            {/* 上传数据集模态框 */}
            <Modal
                title="上传评测数据集"
                open={uploadVisible}
                onCancel={() => {
                    setUploadVisible(false);
                    form.resetFields();
                }}
                footer={null}
                width={600}
            >
                <Form layout="vertical" form={form}>
                    <Form.Item
                        label="数据集名称"
                        name="name"
                        rules={[
                            { required: true, message: '请输入数据集名称' },
                        ]}
                    >
                        <Input placeholder="例如：金融问答数据集" />
                    </Form.Item>

                    <Form.Item label="描述" name="description">
                        <Input.TextArea
                            rows={3}
                            placeholder="简要描述数据集的内容和用途"
                        />
                    </Form.Item>

                    <Form.Item label="上传文件">
                        <Dragger {...uploadProps}>
                            <p className="ant-upload-drag-icon">
                                <DatabaseOutlined
                                    style={{ fontSize: 48, color: '#1890ff' }}
                                />
                            </p>
                            <p className="ant-upload-text">
                                点击或拖拽文件到此区域上传
                            </p>
                            <p className="ant-upload-hint">
                                支持 CSV, JSON, JSONL, Excel, TXT 格式
                                <br />
                                文件大小不超过 10MB
                            </p>
                        </Dragger>
                    </Form.Item>

                    <div style={{ marginTop: 16 }}>
                        <Title level={5}>数据格式要求</Title>
                        <Paragraph>
                            <ul>
                                <li>
                                    <strong>必需字段：</strong>question（问题）
                                </li>
                                <li>
                                    <strong>可选字段：</strong>
                                    expected_answer（参考答案）,
                                    contexts（上下文）
                                </li>
                                <li>CSV 格式：第一行为表头，每行一个样本</li>
                                <li>
                                    JSON 格式：数组形式，每个元素为一个样本对象
                                </li>
                            </ul>
                        </Paragraph>
                    </div>
                </Form>
            </Modal>

            {/* AI 智能生成数据集模态框 */}
            <Modal
                title="AI 智能生成数据集"
                open={generateVisible}
                onOk={handleGenerateSubmit}
                onCancel={closeGenModal}
                confirmLoading={generating}
                okText="生成"
                cancelText="取消"
                width={600}
                okButtonProps={{
                    disabled:
                        !genSelectedConnectionId ||
                        !genCapable ||
                        genConnectionLoading,
                }}
            >
                <Form
                    layout="vertical"
                    form={generateForm}
                    initialValues={{ type: 'ai_generated' }}
                >
                    <Form.Item name="type" initialValue="ai_generated" hidden>
                        <input type="hidden" />
                    </Form.Item>

                    <Form.Item
                        label="选择 RAG 连接"
                        required
                    >
                        {genConnectionLoading ? (
                            <Skeleton.Input active block />
                        ) : genConnectionError ? (
                            <Alert
                                type="error"
                                message={genConnectionError}
                                action={
                                    <Button
                                        size="small"
                                        icon={<ReloadOutlined />}
                                        onClick={loadGenConnections}
                                    >
                                        重试
                                    </Button>
                                }
                            />
                        ) : (
                            <Select
                                placeholder="选择 RAG 系统连接"
                                value={genSelectedConnectionId}
                                onChange={handleGenConnectionChange}
                                options={genConnections.map((c) => ({
                                    value: c.id,
                                    label: `${c.name} (${c.provider})`,
                                    disabled:
                                        !c.enabled ||
                                        !c.capabilities
                                            .generate_dataset_from_knowledge_base,
                                }))}
                            />
                        )}
                    </Form.Item>

                    {genSelectedConnectionId && !genCapable && (
                        <Alert
                            type="warning"
                            showIcon
                            message="该连接不支持 AI 数据集生成"
                            description="请选择其他支持基于知识库生成数据集的 RAG 连接。"
                            style={{ marginBottom: 16 }}
                        />
                    )}

                    {genSelectedConnectionId && genCapable && (
                        <>
                            <Form.Item
                                label="选择知识库"
                                name="kb_id"
                                rules={[
                                    { required: true, message: '请选择知识库' },
                                ]}
                            >
                                <Select
                                    placeholder="选择要基于的知识库"
                                    loading={genKbLoading}
                                    showSearch
                                    filterOption={(input, option) =>
                                        String(option?.label ?? option?.value ?? '')
                                            .toLowerCase()
                                            .includes(input.toLowerCase())
                                    }
                                >
                                    {genKbs.map((kb) => (
                                        <Select.Option key={kb.id} value={kb.id}>
                                            {kb.name}
                                        </Select.Option>
                                    ))}
                                </Select>
                            </Form.Item>

                            <Form.Item
                                label="生成数量"
                                name="sample_count"
                                rules={[
                                    { required: true, message: '请输入生成数量' },
                                ]}
                                initialValue={10}
                            >
                                <InputNumber
                                    min={1}
                                    max={100}
                                    placeholder="建议 10-50 个样本"
                                    style={{ width: '100%' }}
                                />
                            </Form.Item>

                            <Form.Item
                                label="问题类型"
                                name="question_types"
                                initialValue={['factual', 'analytical']}
                            >
                                <Select
                                    mode="multiple"
                                    placeholder="选择要生成的问题类型"
                                    options={[
                                        { label: '事实性问题', value: 'factual' },
                                        { label: '分析性问题', value: 'analytical' },
                                        { label: '应用性问题', value: 'application' },
                                        { label: '比较性问题', value: 'comparison' },
                                        { label: '解释性问题', value: 'explanation' },
                                    ]}
                                />
                            </Form.Item>
                        </>
                    )}

                    <div style={{ marginTop: 16 }}>
                        <Title level={5}>说明</Title>
                        <Paragraph>
                            <ul>
                                <li>
                                    基于选择的知识库内容，通过大模型智能生成问答数据
                                </li>
                                <li>
                                    自动提取知识库chunks，生成高质量的问题和答案
                                </li>
                                <li>
                                    支持多种问题类型：事实性、分析性、应用性等
                                </li>
                                <li>
                                    生成的数据包含问题、标准答案和相关上下文
                                </li>
                                <li>
                                    建议生成数量：10-50个样本，确保质量和多样性
                                </li>
                            </ul>
                        </Paragraph>
                    </div>
                </Form>
            </Modal>

            {/* 预览数据集模态框 */}
            <Modal
                title={`预览数据集：${selectedDataset?.name}`}
                open={previewVisible}
                onCancel={() => setPreviewVisible(false)}
                width={900}
                footer={[
                    <Button
                        key="close"
                        onClick={() => setPreviewVisible(false)}
                    >
                        关闭
                    </Button>,
                ]}
            >
                {selectedDataset && (
                    <Tabs defaultActiveKey="samples">
                        <Tabs.TabPane tab="基本信息" key="info">
                            <Descriptions column={2}>
                                <Descriptions.Item label="数据集ID">
                                    {selectedDataset.id}
                                </Descriptions.Item>
                                <Descriptions.Item label="文件类型">
                                    {selectedDataset.file_type.toUpperCase()}
                                </Descriptions.Item>
                                <Descriptions.Item label="样本数量">
                                    {selectedDataset.num_samples}
                                </Descriptions.Item>
                                <Descriptions.Item label="包含参考答案">
                                    {selectedDataset.has_reference
                                        ? '是'
                                        : '否'}
                                </Descriptions.Item>
                                <Descriptions.Item label="包含上下文">
                                    {selectedDataset.has_contexts ? '是' : '否'}
                                </Descriptions.Item>
                                <Descriptions.Item label="创建时间">
                                    {new Date(
                                        selectedDataset.created_at,
                                    ).toLocaleString('zh-CN')}
                                </Descriptions.Item>
                                <Descriptions.Item label="创建者">
                                    {selectedDataset.created_by}
                                </Descriptions.Item>
                                <Descriptions.Item label="描述" span={2}>
                                    {selectedDataset.description || '-'}
                                </Descriptions.Item>
                            </Descriptions>
                        </Tabs.TabPane>
                        <Tabs.TabPane tab="数据样例" key="samples">
                            {samplesLoading ? (
                                <div
                                    style={{
                                        textAlign: 'center',
                                        padding: '40px',
                                    }}
                                >
                                    <Spin tip="加载样本数据中..." />
                                </div>
                            ) : (
                                <List
                                    dataSource={datasetSamples}
                                    locale={{ emptyText: '暂无样本数据' }}
                                    renderItem={(item, index) => (
                                        <List.Item>
                                            <List.Item.Meta
                                                title={
                                                    <Text strong>
                                                        样本 {index + 1}：
                                                    </Text>
                                                }
                                                description={
                                                    <Space
                                                        direction="vertical"
                                                        style={{
                                                            width: '100%',
                                                        }}
                                                    >
                                                        <div>
                                                            <Text type="secondary">
                                                                问题：
                                                            </Text>
                                                            <Text>
                                                                {item.question}
                                                            </Text>
                                                        </div>
                                                        {item.expected_answer && (
                                                            <div>
                                                                <Text type="secondary">
                                                                    参考答案：
                                                                </Text>
                                                                <Text>
                                                                    {
                                                                        item.expected_answer
                                                                    }
                                                                </Text>
                                                            </div>
                                                        )}
                                                        {item.contexts &&
                                                            item.contexts
                                                                .length > 0 && (
                                                                <div>
                                                                    <Text type="secondary">
                                                                        上下文：
                                                                    </Text>
                                                                    <Text>
                                                                        {item.contexts.join(
                                                                            ', ',
                                                                        )}
                                                                    </Text>
                                                                </div>
                                                            )}
                                                    </Space>
                                                }
                                            />
                                        </List.Item>
                                    )}
                                />
                            )}
                        </Tabs.TabPane>
                    </Tabs>
                )}
            </Modal>

            {/* 创建评测任务模态框 */}
            <Modal
                title="创建评测任务"
                open={createTaskVisible}
                onCancel={() => setCreateTaskVisible(false)}
                footer={null}
                width={700}
                destroyOnClose
            >
                <EvaluationTaskForm
                    initialDatasetId={selectedDataset?.id}
                    onCreated={() => setCreateTaskVisible(false)}
                    onCancel={() => setCreateTaskVisible(false)}
                />
            </Modal>
        </div>
    );
};

export default Datasets;
