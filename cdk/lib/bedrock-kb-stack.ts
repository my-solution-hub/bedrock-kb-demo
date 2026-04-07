import * as cdk from "aws-cdk-lib";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3deploy from "aws-cdk-lib/aws-s3-deployment";
import { bedrock } from "@cdklabs/generative-ai-cdk-constructs";
import { Construct } from "constructs";
import * as path from "path";

export class BedrockKbStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // --- S3 Bucket for knowledge base content ---
    const bucket = new s3.Bucket(this, "KbContentBucket", {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    new s3deploy.BucketDeployment(this, "DeployContent", {
      sources: [s3deploy.Source.asset(path.join(__dirname, "../../content"))],
      destinationBucket: bucket,
    });

    // --- Knowledge Base (AOSS collection + index created automatically) ---
    const kb = new bedrock.VectorKnowledgeBase(this, "KnowledgeBase", {
      embeddingsModel: bedrock.BedrockFoundationModel.COHERE_EMBED_MULTILINGUAL_V3,
      instruction:
        "Use this knowledge base to answer questions about strange fictional stories. " +
        "It contains unique facts in English, Chinese, and German.",
    });

    // --- S3 Data Source ---
    new bedrock.S3DataSource(this, "DataSource", {
      bucket,
      knowledgeBase: kb,
      dataSourceName: "story-content",
      chunkingStrategy: bedrock.ChunkingStrategy.fixedSize({
        maxTokens: 1000,
        overlapPercentage: 25,
      }),
    });

    // --- Outputs ---
    new cdk.CfnOutput(this, "KnowledgeBaseId", {
      value: kb.knowledgeBaseId,
    });
    new cdk.CfnOutput(this, "BucketName", {
      value: bucket.bucketName,
    });
  }
}
