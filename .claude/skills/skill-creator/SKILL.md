---
name: skill-creator
description: 创建有效 skills 的指南。当用户想要创建新 skill（或更新现有 skill）以扩展 Claude 的专业知识、工作流或工具集成能力时使用此 skill。
---

# Skill Creator

## 关于 Skills

Skills 是模块化、自包含的包，通过提供专业知识、工作流和工具来扩展 Claude 的能力。

### Skills 提供什么

1. **专业工作流** - 特定领域的多步骤流程
2. **工具集成** - 处理特定文件格式或 API 的说明
3. **领域专业知识** - 公司特定知识、模式、业务逻辑
4. **捆绑资源** - 脚本、参考资料和复杂重复任务的资产

## 核心原则

### 简洁是关键

上下文窗口是公共资源。Skills 与 Claude 需要的其他所有内容共享上下文窗口。

**默认假设**: Claude 已经非常聪明。只添加 Claude 不知道的上下文。

### Skill 结构

```
skill-name/
├── SKILL.md (必需)
│   ├── YAML frontmatter 元数据 (必需)
│   │   ├── name: (必需)
│   │   └── description: (必需)
│   └── Markdown 说明 (必需)
└── 捆绑资源 (可选)
    ├── scripts/          - 可执行代码
    ├── references/       - 参考文档
    └── assets/           - 输出中使用的文件
```

### Frontmatter 字段

- `name`: skill 名称，也是 `/slash-command` 名称
- `description`: 功能描述，Claude 用它判断何时使用该 skill

## Skill 创建流程

1. **理解 skill** - 通过具体示例理解
2. **规划可复用内容** - 确定 scripts、references、assets
3. **初始化 skill** - 创建目录结构
4. **编辑 skill** - 实现资源并编写 SKILL.md
5. **迭代** - 基于实际使用改进

## 编写指南

- 使用祈使句/不定式形式
- 保持 SKILL.md 简洁，不超过 500 行
- 将详细内容拆分到 references 文件
- 避免创建不必要的辅助文档（如 README.md、CHANGELOG.md）

## 渐进式披露

Skills 使用三级加载系统有效管理上下文：

1. **元数据** - 始终在上下文中（~100 词）
2. **SKILL.md 正文** - 触发时加载（<5k 词）
3. **捆绑资源** - 按需加载（无限制）
