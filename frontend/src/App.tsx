import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import {
    App as AntApp,
    Button,
    ConfigProvider,
    Grid,
    Layout,
    Menu,
    Tooltip,
    Typography,
    theme,
} from 'antd';
import {
    BulbOutlined,
    DashboardOutlined,
    DatabaseOutlined,
    ExperimentOutlined,
    FileTextOutlined,
    MenuFoldOutlined,
    MenuUnfoldOutlined,
    MoonOutlined,
    SettingOutlined,
} from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';
import './App.css';

import Dashboard from './pages/Dashboard';
import Datasets from './pages/Datasets';
import Tasks from './pages/Tasks';
import Reports from './pages/Reports';
import Settings from './pages/Settings';

const { Header, Sider, Content } = Layout;
const { Text, Title } = Typography;

type ThemeMode = 'light' | 'dark';

const routeMeta = [
    { key: 'dashboard', path: '/', title: '评测仪表盘' },
    { key: 'datasets', path: '/datasets', title: '数据集管理' },
    { key: 'tasks', path: '/tasks', title: '评测任务' },
    { key: 'reports', path: '/reports', title: '评测报告' },
    { key: 'settings', path: '/settings', title: '系统设置' },
];

const getInitialTheme = (): ThemeMode => {
    const storedTheme = window.localStorage.getItem('smart-eval-theme');
    if (storedTheme === 'light' || storedTheme === 'dark') {
        return storedTheme;
    }

    return window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light';
};

const ThemeContext = React.createContext<{
    mode: ThemeMode;
    toggle: () => void;
}>({ mode: 'light', toggle: () => undefined });

const ThemeToggle: React.FC = () => {
    const { mode, toggle } = React.useContext(ThemeContext);
    const label = mode === 'dark' ? '切换浅色模式' : '切换深色模式';

    return (
        <Tooltip title={label}>
            <Button
                className="theme-toggle"
                aria-label={label}
                icon={mode === 'dark' ? <BulbOutlined /> : <MoonOutlined />}
                onClick={toggle}
            />
        </Tooltip>
    );
};

const AppLayout: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const screens = Grid.useBreakpoint();
    const [collapsed, setCollapsed] = React.useState(false);

    React.useEffect(() => {
        if (screens.lg !== undefined) {
            setCollapsed(!screens.lg);
        }
    }, [screens.lg]);

    const currentRoute =
        routeMeta.find((route) => route.path === location.pathname) ||
        routeMeta[0];

    const menuItems = [
        {
            key: 'dashboard',
            icon: <DashboardOutlined />,
            label: '评测仪表盘',
            onClick: () => navigate('/'),
        },
        {
            key: 'datasets',
            icon: <DatabaseOutlined />,
            label: '数据集管理',
            onClick: () => navigate('/datasets'),
        },
        {
            key: 'tasks',
            icon: <ExperimentOutlined />,
            label: '评测任务',
            onClick: () => navigate('/tasks'),
        },
        {
            key: 'reports',
            icon: <FileTextOutlined />,
            label: '评测报告',
            onClick: () => navigate('/reports'),
        },
        {
            key: 'settings',
            icon: <SettingOutlined />,
            label: '系统设置',
            onClick: () => navigate('/settings'),
        },
    ];

    return (
        <Layout className="app-layout">
            <Sider
                collapsed={collapsed}
                collapsedWidth={76}
                className="app-sider"
                trigger={null}
                width={248}
            >
                <div className="brand-lockup">
                    <div className="brand-mark" aria-hidden="true">
                        <ExperimentOutlined />
                    </div>
                    {!collapsed && (
                        <div className="brand-copy">
                            <Title level={4}>Smart Eval</Title>
                            <Text>知识库质量中心</Text>
                        </div>
                    )}
                </div>
                <Menu
                    theme="dark"
                    mode="inline"
                    selectedKeys={[currentRoute.key]}
                    items={menuItems}
                    className="app-menu"
                />
                {!collapsed && (
                    <div className="sider-note">
                        <Text>评测流程</Text>
                        <strong>数据集 / 任务 / 报告</strong>
                    </div>
                )}
            </Sider>
            <Layout className="app-main-layout">
                <Header className="app-header">
                    <div className="app-header__start">
                        <Button
                            type="text"
                            className="sidebar-toggle"
                            aria-label={collapsed ? '展开导航' : '收起导航'}
                            icon={
                                collapsed ? (
                                    <MenuUnfoldOutlined />
                                ) : (
                                    <MenuFoldOutlined />
                                )
                            }
                            onClick={() => setCollapsed((value) => !value)}
                        />
                        <div className="header-title">
                            <Text type="secondary">RAG 知识库评测中心</Text>
                            <Title level={5}>{currentRoute.title}</Title>
                        </div>
                    </div>
                    <ThemeToggle />
                </Header>
                <Content className="app-content">
                    <div className="app-content__inner">
                        <Routes>
                            <Route path="/" element={<Dashboard />} />
                            <Route path="/datasets" element={<Datasets />} />
                            <Route path="/tasks" element={<Tasks />} />
                            <Route path="/reports" element={<Reports />} />
                            <Route path="/settings" element={<Settings />} />
                            <Route path="*" element={<Navigate to="/" />} />
                        </Routes>
                    </div>
                </Content>
            </Layout>
        </Layout>
    );
};

const App: React.FC = () => {
    const [mode, setMode] = React.useState<ThemeMode>(getInitialTheme);

    React.useEffect(() => {
        document.documentElement.dataset.theme = mode;
        document.documentElement.style.colorScheme = mode;
        window.localStorage.setItem('smart-eval-theme', mode);
    }, [mode]);

    const themeContext = React.useMemo(
        () => ({
            mode,
            toggle: () =>
                setMode((current) =>
                    current === 'dark' ? 'light' : 'dark',
                ),
        }),
        [mode],
    );

    return (
        <ConfigProvider
            theme={{
                algorithm:
                    mode === 'dark'
                        ? theme.darkAlgorithm
                        : theme.defaultAlgorithm,
                token: {
                    colorPrimary: '#356ae6',
                    colorInfo: '#356ae6',
                    colorSuccess: '#138a63',
                    colorWarning: '#c27803',
                    colorError: '#d64b4b',
                    borderRadius: 10,
                    borderRadiusLG: 14,
                    controlHeight: 38,
                    fontFamily:
                        'ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
                },
                components: {
                    Button: {
                        primaryShadow: 'none',
                        defaultShadow: 'none',
                        fontWeight: 600,
                    },
                    Card: {
                        headerFontSize: 15,
                    },
                    Menu: {
                        darkItemBg: 'transparent',
                        darkItemSelectedBg: '#315fd0',
                        darkItemHoverBg: 'rgba(255, 255, 255, 0.08)',
                    },
                    Table: {
                        headerBg:
                            mode === 'dark' ? '#171a22' : '#f6f8fc',
                        headerColor:
                            mode === 'dark' ? '#d7dce8' : '#536076',
                        headerSplitColor: 'transparent',
                        rowHoverBg:
                            mode === 'dark' ? '#191d27' : '#f7f9fd',
                    },
                },
            }}
        >
            <ThemeContext.Provider value={themeContext}>
                <AntApp>
                    <BrowserRouter>
                        <AppLayout />
                    </BrowserRouter>
                </AntApp>
            </ThemeContext.Provider>
        </ConfigProvider>
    );
};

export default App;
