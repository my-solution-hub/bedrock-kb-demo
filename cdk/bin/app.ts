#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { BedrockKbStack } from "../lib/bedrock-kb-stack";

const app = new cdk.App();
new BedrockKbStack(app, "BedrockKbTestStack", {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION ?? "us-east-1",
  },
});
