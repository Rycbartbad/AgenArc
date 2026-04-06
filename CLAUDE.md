# AgenArc 项目指南

## 项目概述

AgenArc 是一个基于有向图的声明式 Agent 编排框架，核心理念是"机制与策略分离"。

**核心哲学：**
- 内核：极致稳定，仅负责安全调度与资源校验
- 自修复/逻辑进化：由用户在图流程内自行构建
- 资产边界：`arc://` 虚拟协议隔离

## 关键文档

| 文档 | 作用 | 阅读优先级 |
|------|------|------------|
| `ARCHITECTURE.md` | 完整架构设计文档 | **必须阅读** |
| `.claude/plans/*.md` | 当前规划文件 | 必须阅读 |

**重要：任何代码变更前，必须先阅读 ARCHITECTURE.md 了解上下文。**

## 架构定性

```
声明式协议 + 模板语法 + 黑板架构 + 自进化资产
```

### 核心文件结构

```
agenarc/
├── protocol/                 # 协议层（JSON Schema 定义）
├── engine/                   # 执行层（核心引擎）
├── vfs/                      # 虚拟文件系统（arc:// 协议）
├── plugins/                  # 插件系统
├── operators/                # 内置算子库
└── graph/                    # 图数据结构
```

### .arc Bundle 结构

```
my_agent.arc/
├── manifest.json           # 资产包元数据
├── flow.json              # 图协议
├── prompts/               # Prompt 模板
├── scripts/               # 可执行脚本
└── assets/                # 静态资源
```

## 开发指南

### 1. 协议层开发

协议层位于 `agenarc/protocol/`：

- `schema.py` - JSON Schema 定义
- `loader.py` - 协议加载器
- `validator.py` - 验证器

### 2. 执行引擎开发

执行引擎位于 `agenarc/engine/`：

- `executor.py` - 核心引擎
- `guardrail.py` - 校验链（Schema + AST）
- `state.py` - 状态管理
- `scheduler.py` - 调度策略

### 3. 自进化系统

新增功能位于：

- `agenarc/vfs/` - VFS 虚拟文件系统
- `agenarc/operators/evolution.py` - 自进化算子
- `agenarc/plugins/hot_loader.py` - 热重载加载器

## 约定

### 代码规范

- 使用 Python type hints
- 异步优先（async/await）
- 遵循 PEP 8

### Git 提交规范

提交信息应清晰描述变更内容。

### 文档更新

- 架构变更必须同步更新 `ARCHITECTURE.md`
- 重大决策应在变更日志中记录

## 阶段里程碑

1. **MVP 引擎** - 线性流 + 基础算子
2. **完整执行引擎** - 条件/循环/并行
3. **自进化资产系统** - .arc Bundle + VFS + 热重载
4. **插件系统** - Hot_Plugin_Loader
5. **可视化平台** - React Canvas IDE
