# Bedrock Knowledge Base 多语言 RAG 演示

本项目演示如何使用 AWS CDK 部署一个支持多语言的 Amazon Bedrock Knowledge Base（知识库），通过 RAG（检索增强生成）模式对英文、中文、德文文档进行问答。

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        CDK 部署阶段                              │
│                                                                 │
│  content/                                                       │
│  ├── the-clockmaker-of-nowhere.txt  (English)                   │
│  ├── the-noodle-wizard-of-chongqing.txt  (中文)                  │
│  └── der-wolkenschmied-von-heidelberg.txt  (Deutsch)            │
│           │                                                     │
│           ▼                                                     │
│      S3 Bucket ──► Bedrock Data Source (1000 tokens/chunk)      │
│                          │                                      │
│                          ▼                                      │
│      OpenSearch Serverless (AOSS)                               │
│      ┌──────────────────────────────────┐                       │
│      │  向量集合 + 向量索引 (自动创建)      │                       │
│      └──────────────────────────────────┘                       │
│                          ▲                                      │
│                          │                                      │
│      Bedrock Knowledge Base                                     │
│      (Cohere Embed Multilingual V3 — 支持 100+ 语言)             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        查询阶段                                  │
│                                                                 │
│  用户提问 (任意语言) ──► RetrieveAndGenerate API                  │
│                              │                                  │
│                              ├─► 1. 向量检索：AOSS 相似度搜索     │
│                              │                                  │
│                              └─► 2. 生成回答：Claude 3 Haiku     │
│                                   基于检索上下文生成答案           │
└─────────────────────────────────────────────────────────────────┘
```

## 项目结构

```
├── content/                                     # 知识库源文档（3 种语言）
│   ├── the-clockmaker-of-nowhere.txt            # 英文奇异故事
│   ├── the-noodle-wizard-of-chongqing.txt       # 中文奇异故事
│   └── der-wolkenschmied-von-heidelberg.txt     # 德文奇异故事
├── cdk/                                         # CDK 基础设施代码
│   ├── bin/app.ts                               # CDK 应用入口
│   └── lib/bedrock-kb-stack.ts                  # 核心 Stack 定义
├── scripts/
│   └── sync-and-query.py                        # 一键同步 + 多语言测试脚本
└── README.md
```

## 工作原理（分步详解）

### 第一步：CDK 定义基础设施

`cdk/lib/bedrock-kb-stack.ts` 使用 `@cdklabs/generative-ai-cdk-constructs` 高级构造库。一个 `VectorKnowledgeBase` 构造会自动创建：

- OpenSearch Serverless 加密策略、网络策略、数据访问策略
- OpenSearch Serverless 向量集合（Collection）
- 向量索引（通过 Lambda 自定义资源自动创建）
- Bedrock Knowledge Base 资源及其关联的 IAM 角色

```typescript
const kb = new bedrock.VectorKnowledgeBase(this, "KnowledgeBase", {
  embeddingsModel: bedrock.BedrockFoundationModel.COHERE_EMBED_MULTILINGUAL_V3,
  instruction: "Use this knowledge base to answer questions about strange fictional stories. "
    + "It contains unique facts in English, Chinese, and German.",
});
```

### 第二步：上传多语言文档到 S3

CDK 的 `BucketDeployment` 在部署时自动将 `content/` 目录下的 3 个故事文件上传到 S3。

### 第三步：关联 S3 数据源

`S3DataSource` 将 S3 桶与知识库关联，配置分块策略（1000 tokens，25% 重叠）。较大的分块确保多语言文本不会在关键信息处被截断。

### 第四步：数据摄取（Ingestion）

运行测试脚本后自动触发：

```
S3 文档 (EN/ZH/DE) ──► 文本分块 ──► 多语言向量嵌入 (Cohere) ──► 存入 AOSS 索引
```

### 第五步：多语言 RAG 查询

脚本通过 `RetrieveAndGenerate` API 进行问答：

```
用户问题 (任意语言) ──► 多语言向量化 ──► AOSS 相似度搜索 ──► 相关片段
                                                              │
                                                              ▼
                                          Claude 3 Haiku + 上下文 ──► 最终答案
```

支持的查询模式：
- 同语言查询：英文问英文故事、中文问中文故事、德文问德文故事
- 跨语言查询：用中文提问英文故事的内容，用英文提问中文/德文故事的内容

## 涉及的 AWS 服务

| 服务 | 用途 |
|------|------|
| Amazon S3 | 存储多语言源文档 |
| Amazon Bedrock Knowledge Base | 管理知识库生命周期、数据摄取、检索 |
| Amazon Bedrock (Cohere Embed Multilingual V3) | 多语言向量嵌入（支持 100+ 语言） |
| Amazon Bedrock (Claude 3 Haiku) | 基于检索上下文生成自然语言回答 |
| Amazon OpenSearch Serverless | 向量数据库，存储和检索向量嵌入 |
| AWS Lambda | 自定义资源，自动创建 AOSS 向量索引 |
| AWS IAM | 服务间权限控制 |

## 故事内容

知识库包含 3 个奇异虚构故事，每个故事都包含只能通过查询知识库才能获得的独特事实：

### 英文：The Clockmaker of Nowhere
- 钟表匠 Elsworth Vane 有 11 根手指（左手 6 根，右手 5 根）
- 三条腿的猫 Professor Zinc 能用降 B 调打喷嚏
- 奶酪潜艇"乳糖不耐受号"由失望图书管理员的叹息驱动
- 白化松鼠邮递员速度 7.3 英里/小时

### 中文：重庆面条巫师
- 六条腿蜥蜴"花椒将军"能用尾巴测量辣度（精确到斯科维尔小数点后四位）
- 量子牛肉面售价 8888 枚雾币
- 醋婆婆的飞行火锅店"酸辣号"由发酵豆腐驱动
- 座右铭："面条是宇宙的密码，汤是解密的钥匙"

### 德文：Der Wolkenschmied von Heidelberg
- 双尾獾 Professor Sauerkraut 有 3 个鼻子
- 雷霆竖琴（Donnerharfe）售价 33,333 Nebelgroschen
- 飞行啤酒屋"Die Glutenfreie Zeppelin"由失望啤酒评委的愤怒驱动
- 座右铭："Wolken sind nur Gedanken, die zu schwer zum Fliegen geworden sind"

## 前置条件

- AWS CLI 已配置凭证和区域
- Node.js >= 18，npm
- Python 3.9+，已安装 `boto3`（`pip install boto3`）
- CDK v2 已在目标账户/区域完成 bootstrap（`npx cdk bootstrap`）
- 在目标区域启用以下模型的访问权限：
  - Cohere Embed Multilingual V3
  - Anthropic Claude 3 Haiku

## 快速开始

### 1. 部署基础设施

```bash
cd cdk
npm install
npx cdk deploy --require-approval never
```

部署约需 5-6 分钟（主要等待 AOSS 集合创建）。完成后记录输出的 `KnowledgeBaseId`。

### 2. 一键同步 + 测试

```bash
# 设置区域（如果 AWS CLI 默认区域不是目标区域）
export AWS_DEFAULT_REGION=ap-southeast-1

# 运行测试（Data Source ID 自动发现，无需手动输入）
python scripts/sync-and-query.py <KnowledgeBaseId>
```

脚本会自动完成：
1. 发现 Data Source ID
2. 触发数据摄取
3. 等待 AOSS 索引刷新（最多 60 秒）
4. 运行 14 个多语言测试查询（英文/中文/德文 + 跨语言）

### 3. 清理资源

```bash
cd cdk && npx cdk destroy --force
```

## 实际测试输出

以下是部署完成后运行测试脚本的真实输出：

> [EN→EN] Q: What was the name of the three-legged cat and what was its special ability?
> ✅ A: The name of the three-legged cat that guarded Elsworth Vane's workshop was Professor Zinc. Professor Zinc had the unusual ability to sneeze in perfect B-flat.
>
> [EN→EN] Q: What powered Madame Fisk submarine?
> ✅ A: Madame Fisk's submarine called "The Lactose Intolerant" was powered by the collective sighs of disappointed librarians.
>
> [ZH→ZH] Q: 蒋铜锅的面条工作室由什么动物守卫？它有什么特殊能力？
> ✅ A: 蒋铜锅的面条工作室由一只名叫"花椒将军"的六条腿蜥蜴守卫。花椒将军的特殊能力是能用尾巴精确测量任何液体的辣度，精确到斯科维尔辣度单位的小数点后四位。
>
> [ZH→ZH] Q: 量子牛肉面的售价是多少雾币？
> ✅ A: 量子牛肉面的售价是每碗8888枚雾币,使其成为重庆地下第七层最昂贵的食物。
>
> [ZH→ZH] Q: 醋婆婆的飞行火锅店叫什么名字？靠什么驱动？
> ✅ A: 醋婆婆经营的飞行火锅店名为"酸辣号"，由发酵豆腐驱动。
>
> [ZH→ZH] Q: 面条工作室的座右铭是什么？
> ✅ A: 面条工作室的座右铭是"面条是宇宙的密码，汤是解密的钥匙"。
>
> [DE→DE] Q: Wie hieß der zweischwänzige Dachs und wie viele Nasen hatte er?
> ✅ A: Der zweischwänzige Dachs hieß Professor Sauerkraut. Er hatte drei Nasen - eine links, eine rechts und eine kleine auf der Stirn.
>
> [DE→DE] Q: Wie viel kostete die Donnerharfe in Nebelgroschen?
> ✅ A: Die Donnerharfe kostete genau 33.333 Nebelgroschen.
>
> [DE→DE] Q: Wie hieß das fliegende Brauhaus von Frau Blitzschlag und was trieb es an?
> ✅ A: Das fliegende Brauhaus hieß "Die Glutenfreie Zeppelin" und wurde angetrieben von der kollektiven Entrüstung enttäuschter Bierrichter.
>
> [DE→DE] Q: Was war das Motto über der Werkstatttür von Balthasar?
> ✅ A: "Wolken sind nur Gedanken, die zu schwer zum Fliegen geworden sind."
>
> [ZH→EN] Q: Elsworth Vane有多少根手指？
> ✅ A: Elsworth Vane had exactly eleven fingers - six on his left hand and five on his right.
>
> [EN→ZH] Q: What animal guards the noodle workshop and what is its special ability?
> ✅ A: The noodle workshop is guarded by a six-legged lizard named "花椒将军" (General Sichuan Pepper), which can precisely measure the spiciness of any liquid with its tail.
>
> [EN→DE] Q: What is the motto above Balthasar's workshop door?
> ✅ A: "Wolken sind nur Gedanken, die zu schwer zum Fliegen geworden sind." (Clouds are just thoughts that have become too heavy to fly.)
