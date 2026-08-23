import { request, uploadFile } from './api';

// 类型定义
export interface Dataset {
    id: string;
    name: string;
    description?: string;
    file_name: string;
    file_type: string;
    num_samples: number;
    has_reference: boolean;
    has_contexts: boolean;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    progress?: number;
    error_message?: string;
    created_at: string;
    created_by: string;
}

export interface DatasetUploadParams {
    name: string;
    description?: string;
}

export interface EvaluationTask {
    id: string;
    name?: string;
    kb_id?: string;
    chat_id?: string;
    assistant_id?: string;
    assistant_name_snapshot?: string;
    dataset_name?: string;
    rag_provider?: RagProvider;
    rag_connection_id?: string;
    source_snapshot?: {
        provider: RagProvider;
        connection_id?: string | null;
        connection_name: string;
        assistant_id: string;
        assistant_name: string;
        knowledge_base_selection_mode?: KnowledgeBaseSelectionMode | null;
        knowledge_bases: Array<{ id: string; name: string }>;
        legacy: boolean;
    };
    dataset_id: string;
    metrics: string[];
    llm_model?: string;
    batch_size?: number;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
    progress: number;
    total_samples: number;
    processed_samples: number;
    created_at: string;
    started_at?: string;
    completed_at?: string;
    error_message?: string;
    outcome?: 'succeeded' | 'partially_succeeded' | 'failed' | 'cancelled';
    has_warnings?: boolean;
    failed_sample_count?: number;
    scored_sample_count?: number;
}

export interface DatasetSample {
    question: string;
    expected_answer?: string;
    contexts?: string[];
    reference_contexts?: string[];
    [key: string]: unknown;
}

export interface DatasetSamplePage {
    samples: DatasetSample[];
    total: number;
    offset: number;
    limit: number;
}

export interface TaskCreateParams {
    name?: string;
    chat_id?: string; // legacy RAGFlow compatibility
    dataset_id: string;
    metrics: string[];
    llm_model?: string;
    batch_size?: number;
    rag_target?: RagTarget;
}

export type RagProvider = 'ragflow' | 'intelliq';
export type KnowledgeBaseSelectionMode = 'all' | 'selected' | 'none';

export interface RagTarget {
    provider: RagProvider;
    connection_id: string;
    assistant_id: string;
    knowledge_base_ids?: string[];
}

export interface RagConnectionSummary {
    id: string;
    provider: RagProvider;
    name: string;
    api_url: string;
    api_key_configured: boolean;
    editable: boolean;
    enabled: boolean;
    status: 'untested' | 'available' | 'unavailable';
    revision: number;
    capabilities: {
        list_knowledge_bases: boolean;
        list_assistants: boolean;
        select_multiple_knowledge_bases: boolean;
        generate_dataset_from_knowledge_base: boolean;
        streaming_chat: boolean;
    };
    last_tested_at?: string;
    error?: { category: string; message: string; retryable: boolean } | null;
}

export interface RagResourceRef {
    id: string;
    provider: RagProvider;
    connection_id: string;
    name: string;
    description?: string;
    selectable: boolean;
    disabled_reason?: string | null;
}

export interface AssistantRef extends RagResourceRef {
    built_in?: boolean | null;
    knowledge_base_selection_mode: KnowledgeBaseSelectionMode | null;
    allowed_knowledge_base_ids?: string[];
}

export interface EvaluationReport {
    task_id: string;
    kb_name: string;
    dataset_name: string;
    overall_score: number;
    metric_scores: {
        [key: string]: {
            mean: number;
            std: number;
            min: number;
            max: number;
        };
    };
    summary: string;
    recommendations: string[];
    createdAt: string;
    successRate?: number;
    totalSamples?: number;
    lowScoreSamples?: Array<{
        question: string;
        score: number;
        issue: string;
    }>;
    detailed_scores?: Array<{
        user_input: string;
        actual_answer: string;
        expected_answer: string;
        contexts: string[];
        completion_status?: string;
        partial_answer?: string;
        upstream_error?: { category: string; message: string; retryable?: boolean } | null;
        [key: string]: any; // for metric scores
    }>;
    rag_provider?: RagProvider;
    rag_connection_id?: string | null;
    assistant_id?: string | null;
    knowledge_base_ids?: string[];
    source_snapshot?: {
        connection_name: string;
        assistant_name: string;
        knowledge_base_selection_mode?: KnowledgeBaseSelectionMode | null;
        knowledge_bases: Array<{ id: string; name: string }>;
    };
    scoredSamples?: number;
    failedSamples?: number;
    warning?: { code: string; message: string; failed_samples: number } | null;
    status?: string;
}

export interface Metric {
    name: string;
    display_name: string;
    description: string;
    type: 'llm_based' | 'traditional' | 'custom';
    requires_reference: boolean;
    requires_contexts: boolean;
    default_enabled: boolean;
}

export interface QuickEvaluateParams {
    question: string;
    answer: string;
    contexts?: string[];
    metric?: string;
}

// 数据集相关 API
export const datasetApi = {
    // 上传数据集
    upload: (file: File, params: DatasetUploadParams) => {
        return uploadFile('/evaluation/datasets', file, params);
    },

    // 获取数据集列表
    list: (params?: { offset?: number; limit?: number }) => {
        return request.get<{
            datasets: Dataset[];
            total: number;
            offset: number;
            limit: number;
        }>('/evaluation/datasets', { params });
    },

    // 获取数据集详情
    get: (datasetId: string) => {
        return request.get<Dataset>(`/evaluation/datasets/${datasetId}`);
    },

    // 获取数据集样本
    getSamples: (
        datasetId: string,
        params?: { offset?: number; limit?: number },
    ) => {
        return request.get<DatasetSamplePage>(
            `/evaluation/datasets/${datasetId}/samples`,
            { params },
        );
    },

    // 删除数据集
    delete: (datasetId: string) => {
        return request.delete(`/evaluation/datasets/${datasetId}`);
    },

    // 批量删除数据集
    batchDelete: (datasetIds: string[]) => {
        return request.delete<{
            message: string;
            deleted_count: number;
            total_count: number;
            failed_count: number;
            failed_ids?: string[];
        }>('/evaluation/datasets/batch', { dataset_ids: datasetIds });
    },

    // 生成示例数据集
    generateSample: (type: 'basic' | 'with_reference' | 'with_contexts') => {
        return request.post<Dataset>(`/evaluation/datasets/generate/${type}`);
    },

    // AI生成数据集
    generateAIDataset: (params: {
        kb_id: string;
        sample_count: number;
        question_types: string[];
        connection_id?: string;
    }) => {
        return request.post<Dataset>(
            '/evaluation/datasets/generate/ai',
            params,
        );
    },
};

// 评测任务相关 API
export const taskApi = {
    // 创建评测任务
    create: (params: TaskCreateParams) => {
        return request.post<EvaluationTask>('/evaluation/tasks', params);
    },

    // 获取任务列表
    list: (params?: { status?: string; offset?: number; limit?: number }) => {
        return request.get<{
            tasks: EvaluationTask[];
            total: number;
            offset: number;
            limit: number;
        }>('/evaluation/tasks', { params });
    },

    // 获取任务状态
    getStatus: (taskId: string) => {
        return request.get<EvaluationTask>(`/evaluation/tasks/${taskId}`);
    },

    // 开始任务
    start: (taskId: string) => {
        return request.post(`/evaluation/tasks/${taskId}/start`);
    },

    // 暂停任务
    pause: (taskId: string) => {
        return request.post(`/evaluation/tasks/${taskId}/pause`);
    },

    // 取消任务
    cancel: (taskId: string) => {
        return request.post(`/evaluation/tasks/${taskId}/cancel`);
    },

    // 重试任务
    retry: (taskId: string) => {
        return request.post(`/evaluation/tasks/${taskId}/retry`);
    },

    // 删除任务
    delete: (taskId: string) => {
        return request.delete(`/evaluation/tasks/${taskId}`);
    },

    // 批量删除任务
    batchDelete: (taskIds: string[]) => {
        return request.delete<{
            message: string;
            deleted_count: number;
            total_count: number;
            failed_count: number;
            running_count: number;
            failed_ids?: string[];
            running_tasks?: string[];
        }>('/evaluation/tasks/batch', { task_ids: taskIds });
    },
};

// 报告相关 API
export const reportApi = {
    // 获取评测报告
    get: (taskId: string) => {
        return request.get<EvaluationReport>(`/evaluation/reports/${taskId}`);
    },

    // 导出报告
    export: (taskId: string, format: 'pdf' | 'excel' | 'json') => {
        return request.get(`/evaluation/reports/${taskId}/export`, {
            params: { format },
            responseType: 'blob',
        });
    },

    // 获取报告列表
    list: (params?: {
        rag_provider?: RagProvider;
        rag_connection_id?: string;
        assistant_id?: string;
        knowledge_base_id?: string;
        start_date?: string;
        end_date?: string;
        offset?: number;
        limit?: number;
    }) => {
        return request.get<{
            reports: EvaluationReport[];
            total: number;
            offset: number;
            limit: number;
        }>('/evaluation/reports', {
            params,
        });
    },

    // 删除报告
    delete: (taskId: string) => {
        return request.delete(`/evaluation/reports/${taskId}`);
    },

    // 批量删除报告
    batchDelete: (taskIds: string[]) => {
        return request.delete<{
            message: string;
            deleted_count: number;
            total_count: number;
            failed_count: number;
        }>('/evaluation/reports/batch', { task_ids: taskIds });
    },

    // 对比报告
    compare: (taskIds: string[]) => {
        return request.post('/evaluation/reports/compare', {
            task_ids: taskIds,
        });
    },
};

// 指标相关 API
export const metricApi = {
    // 获取可用指标列表
    list: (type?: 'llm_based' | 'traditional' | 'custom') => {
        return request.get<{ metrics: Metric[] }>('/evaluation/metrics', {
            params: type ? { type } : undefined,
        });
    },

    // 获取指标分组
    getGroups: () => {
        return request.get<{
            groups: {
                [key: string]: Metric[];
            };
        }>('/evaluation/metrics/groups');
    },

    // 验证指标配置
    validate: (
        metrics: string[],
        hasReference: boolean,
        hasContexts: boolean,
    ) => {
        return request.post('/evaluation/metrics/validate', {
            metrics,
            has_reference: hasReference,
            has_contexts: hasContexts,
        });
    },
};

// 快速评测 API
export const quickEvaluateApi = {
    // 快速评测单个问答对
    evaluate: (params: QuickEvaluateParams) => {
        return request.post<{ score: number; metric: string }>(
            '/evaluation/quick',
            params,
        );
    },

    // 批量快速评测
    batchEvaluate: (samples: QuickEvaluateParams[]) => {
        return request.post<{
            results: Array<{ score: number; metric: string }>;
        }>('/evaluation/quick/batch', { samples });
    },
};

// 系统相关 API
export const systemApi = {
    // 健康检查
    health: () => {
        return request.get<{
            status: string;
            service: string;
            timestamp: string;
            metrics_available: number;
        }>('/evaluation/health');
    },

    // 获取系统统计
    getStatistics: () => {
        return request.get('/evaluation/statistics');
    },

    // 获取配置
    getConfig: () => {
        return request.get('/evaluation/config');
    },

    // 更新配置
    updateConfig: (config: any) => {
        return request.put('/evaluation/config', config);
    },

    // 测试API连接
    testConnection: () => {
        return request.post<{
            success: boolean;
            message: string;
            details?: any;
        }>('/evaluation/test-connection', {});
    },
};

export const ragConnectionApi = {
    list: () =>
        request.get<{ connections: RagConnectionSummary[] }>(
            '/evaluation/rag-connections',
        ),
    create: (
        data: {
            provider: 'intelliq';
            name: string;
            api_url: string;
            api_key: string;
            enabled?: boolean;
        },
        adminToken: string,
    ) =>
        request.post<RagConnectionSummary>('/evaluation/rag-connections', data, {
            headers: { Authorization: `Bearer ${adminToken}` },
        }),
    update: (
        id: string,
        data: Partial<{
            name: string;
            api_url: string;
            api_key: string;
            enabled: boolean;
        }>,
        adminToken: string,
    ) =>
        request.put<RagConnectionSummary>(
            `/evaluation/rag-connections/${id}`,
            data,
            { headers: { Authorization: `Bearer ${adminToken}` } },
        ),
    test: (id: string, adminToken: string) =>
        request.post<{
            status: 'available';
            knowledge_base_count: number;
            assistant_count: number;
            tested_at: string;
        }>(`/evaluation/rag-connections/${id}/test`, undefined, {
            headers: { Authorization: `Bearer ${adminToken}` },
        }),
};

export const ragResourceApi = {
    listKnowledgeBases: (
        connectionId: string,
        params?: { search?: string; assistant_id?: string; limit?: number },
    ) =>
        request.get<{
            provider: RagProvider;
            connection_id: string;
            items: RagResourceRef[];
            total: number;
        }>(
            `/evaluation/rag-connections/${connectionId}/knowledge-bases`,
            { params },
        ),
    listAssistants: (
        connectionId: string,
        params?: { search?: string; limit?: number },
    ) =>
        request.get<{
            provider: RagProvider;
            connection_id: string;
            items: AssistantRef[];
            total: number;
        }>(`/evaluation/rag-connections/${connectionId}/assistants`, { params }),
};

// 知识库相关 API
export const knowledgeBaseApi = {
    // 获取知识库列表
    list: async (params?: {
        current_page?: number;
        size?: number;
        name?: string;
    }) => {
        const response = await request.get('/evaluation/knowledgebases', {
            params,
        });
        return response;
    },

    // 获取知识库详情
    get: async (kbId: string) => {
        const response = await request.get(
            `/evaluation/knowledgebases/${kbId}`,
        );
        return response;
    },
};

// Legacy Chat API facade backed by the provider-neutral backend.
export const chatApi = {
    // 获取 Chat 助手列表
    list: async (params?: {
        page?: number;
        page_size?: number;
        name?: string;
    }) => {
        const connections = await ragConnectionApi.list();
        const ragflow = connections.connections.find(
            (item) => item.provider === 'ragflow',
        );
        if (!ragflow) return { code: 0, data: [], message: '' };
        const response = await ragResourceApi.listAssistants(ragflow.id, {
            search: params?.name,
            limit: params?.page_size || 100,
        });
        return {
            code: 0,
            message: '',
            data: response.items.map((item) => ({
                ...item,
                datasets: item.allowed_knowledge_base_ids || [],
            })),
        };
    },

    // 获取 Chat 助手详情
    get: async (chatId: string) => {
        const response = await chatApi.list({ page: 1, page_size: 100 });
        return {
            code: 0,
            message: '',
            data: response.data.find((item: any) => item.id === chatId),
        };
    },
};
