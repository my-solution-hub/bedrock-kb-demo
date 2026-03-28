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
      embeddingsModel: bedrock.BedrockFoundationModel.COHERE_EMBED_ENGLISH_V3,
      instruction:
        "Use this knowledge base to answer questions about a strange fictional story. " +
        "It contains unique facts that cannot be found anywhere else.",
    });

    // --- S3 Data Source ---
    new bedrock.S3DataSource(this, "DataSource", {
      bucket,
      knowledgeBase: kb,
      dataSourceName: "story-content",
      chunkingStrategy: bedrock.ChunkingStrategy.fixedSize({
        maxTokens: 500,
        overlapPercentage: 20,
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
