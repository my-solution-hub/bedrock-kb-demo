# Bedrock Knowledge Base 端到端演示

本项目演示如何使用 AWS CDK 部署一个完整的 Amazon Bedrock Knowledge Base（知识库），并通过 RAG（检索增强生成）模式对自定义文档进行问答。

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        CDK 部署阶段                              │
│                                                                 │
│  content/story.txt ──► S3 Bucket ──► Bedrock Data Source        │
│                                          │                      │
│                                          ▼                      │
│                    OpenSearch Serverless (AOSS)                  │
│                    ┌──────────────────────────┐                  │
│                    │  向量集合 (Vector Collection) │              │
│                    │  向量索引 (bedrock-kb-index)  │              │
│                    └──────────────────────────┘                  │
│                                          ▲                      │
│                                          │                      │
│                    Bedrock Knowledge Base ┘                      │
│                    (Cohere Embed English V3)                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        查询阶段                                  │
│                                                                 │
│  用户提问 ──► RetrieveAndGenerate API                            │
│                    │                                            │
│                    ├─► 1. 向量检索：从 AOSS 中找到相关文档片段      │
│                    │                                            │
│                    └─► 2. 生成回答：Claude 3 Haiku 基于检索       │
│                         到的上下文生成最终答案                     │
└─────────────────────────────────────────────────────────────────┘
```

## 项目结构

```
├── content/                            # 知识库源文档
│   └── the-clockmaker-of-nowhere.txt   # 一个奇异的虚构故事
├── cdk/                                # CDK 基础设施代码 (TypeScript)
│   ├── bin/app.ts                      # CDK 应用入口
│   └── lib/bedrock-kb-stack.ts         # 核心 Stack 定义
├── scripts/
│   └── sync-and-query.py              # 数据同步 + 测试查询脚本
└── README.md
```

## 工作原理（分步详解）

### 第一步：CDK 定义基础设施

`cdk/lib/bedrock-kb-stack.ts` 使用 `@cdklabs/generative-ai-cdk-constructs` 高级构造库定义所有资源。该库封装了大量底层细节，一个 `VectorKnowledgeBase` 构造会自动创建：

- OpenSearch Serverless 加密策略、网络策略、数据访问策略
- OpenSearch Serverless 向量集合（Collection）
- 向量索引（通过 Lambda 自定义资源自动创建）
- Bedrock Knowledge Base 资源及其关联的 IAM 角色

```typescript
// 核心代码只需几行
const kb = new bedrock.VectorKnowledgeBase(this, "KnowledgeBase", {
  embeddingsModel: bedrock.BedrockFoundationModel.COHERE_EMBED_ENGLISH_V3,
  instruction: "Use this knowledge base to answer questions about a strange fictional story.",
});
```

### 第二步：上传文档到 S3

CDK 的 `BucketDeployment` 构造在部署时自动将 `content/` 目录下的文件上传到 S3 桶中。这个 S3 桶作为 Bedrock Data Source 的数据来源。

```typescript
const bucket = new s3.Bucket(this, "KbContentBucket", {
  removalPolicy: cdk.RemovalPolicy.DESTROY,
  autoDeleteObjects: true,
});

new s3deploy.BucketDeployment(this, "DeployContent", {
  sources: [s3deploy.Source.asset(path.join(__dirname, "../../content"))],
  destinationBucket: bucket,
});
```

### 第三步：关联 S3 数据源

`S3DataSource` 将 S3 桶与知识库关联，并配置文档分块策略。本项目使用固定大小分块（500 tokens，20% 重叠），确保检索时能获取足够的上下文。

```typescript
new bedrock.S3DataSource(this, "DataSource", {
  bucket,
  knowledgeBase: kb,
  dataSourceName: "story-content",
  chunkingStrategy: bedrock.ChunkingStrategy.fixedSize({
    maxTokens: 500,
    overlapPercentage: 20,
  }),
});
```

### 第四步：数据摄取（Ingestion）

部署完成后，运行 `sync-and-query.py` 脚本触发数据摄取流程：

1. 调用 `StartIngestionJob` API 启动摄取任务
2. Bedrock 从 S3 读取文档
3. 使用 Cohere Embed English V3 模型将文本转换为向量嵌入
4. 将向量存储到 OpenSearch Serverless 索引中

```
S3 文档 ──► 文本分块 ──► 向量嵌入 (Cohere) ──► 存入 AOSS 索引
```

### 第五步：检索增强生成（RAG 查询）

脚本通过 `RetrieveAndGenerate` API 进行问答，该 API 内部执行两个步骤：

1. 检索（Retrieve）：将用户问题转换为向量，在 AOSS 中进行相似度搜索，找到最相关的文档片段
2. 生成（Generate）：将检索到的文档片段作为上下文，连同用户问题一起发送给 Claude 3 Haiku，生成最终答案

```
用户问题 ──► 向量化 ──► AOSS 相似度搜索 ──► 相关片段
                                              │
                                              ▼
                              Claude 3 Haiku + 上下文 ──► 最终答案
```

## 涉及的 AWS 服务

| 服务 | 用途 |
|------|------|
| Amazon S3 | 存储源文档（故事文本） |
| Amazon Bedrock Knowledge Base | 管理知识库生命周期、数据摄取、检索 |
| Amazon Bedrock (Cohere Embed English V3) | 将文本转换为 1024 维向量嵌入 |
| Amazon Bedrock (Claude 3 Haiku) | 基于检索上下文生成自然语言回答 |
| Amazon OpenSearch Serverless | 向量数据库，存储和检索向量嵌入 |
| AWS Lambda | 自定义资源，自动创建 AOSS 向量索引 |
| AWS IAM | 服务间权限控制 |

## 故事内容

知识库中包含一个名为《虚无之地的钟表匠》的奇异虚构故事，其中包含多个独特的事实，只有通过查询知识库才能获得答案：

- 钟表匠 Elsworth Vane 有 11 根手指（左手 6 根，右手 5 根）
- 时钟显示"时间的味道"：酸涩的早晨、天鹅绒黄昏、松脆的午夜、液态星期四
- 货币叫"耳语硬币"（Whisper Coins），由压缩雾气铸造
- 三条腿的猫叫 Professor Zinc，能用完美的降 B 调打喷嚏
- 奶酪潜艇叫"乳糖不耐受号"，由失望图书管理员的集体叹息驱动
- 白化松鼠邮递员以 7.3 英里/小时的速度穿越地下隧道
- Elsworth 以降 E 小调持续 47 秒的约德尔唱法赢得决斗

## 前置条件

- AWS CLI 已配置凭证
- Node.js >= 18，npm
- Python 3.9+，已安装 `boto3`
- CDK v2 已在目标账户/区域完成 bootstrap（`npx cdk bootstrap`）
- 在目标区域启用了 Cohere Embed English V3 和 Claude 3 Haiku 的模型访问权限

## 部署步骤

```bash
# 1. 安装 CDK 依赖
cd cdk && npm install

# 2. 部署 Stack（约 5-6 分钟，主要等待 AOSS 集合创建）
npx cdk deploy --require-approval never

# 3. 记录输出的 KnowledgeBaseId 和 BucketName
```

## 同步数据并查询

```bash
# 获取 Data Source ID
aws bedrock-agent list-data-sources \
  --knowledge-base-id <KnowledgeBaseId> \
  --query 'dataSourceSummaries[0].dataSourceId' \
  --output text

# 运行同步和查询脚本
python scripts/sync-and-query.py <KnowledgeBaseId> <DataSourceId>
```

## 示例问答结果

| 问题 | 回答 |
|------|------|
| Elsworth Vane 有多少根手指？ | 11 根——左手 6 根，右手 5 根 |
| 三条腿的猫叫什么？有什么特殊能力？ | Professor Zinc，能用完美的降 B 调打喷嚏 |
| Madame Fisk 的潜艇叫什么？靠什么驱动？ | "乳糖不耐受号"，靠失望图书管理员的集体叹息驱动 |
| 邮政松鼠的速度是多少？ | 7.3 英里/小时 |
| 工坊门上刻的座右铭是什么？ | "时间只是我们都同意忽略的一个建议" |
| 改装后的矛盾钟摆值多少耳语硬币？ | 14,000 枚耳语硬币 |
| 矛盾钟摆显示哪些"时间的味道"？ | 酸涩的早晨、天鹅绒黄昏、松脆的午夜、液态星期四 |

## 清理资源

```bash
cd cdk && npx cdk destroy
```
