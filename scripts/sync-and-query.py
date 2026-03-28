"""
Syncs the Bedrock Knowledge Base data source, waits for ingestion,
then runs sample queries to verify the KB works.

Usage:
  python scripts/sync-and-query.py <knowledge-base-id> <data-source-id>
"""

import sys
import time
import json
import boto3

def wait_for_sync(client, kb_id, ds_id, ingestion_job_id):
    """Poll until ingestion job completes."""
    print("Waiting for ingestion to complete...")
    while True:
        resp = client.get_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            ingestionJobId=ingestion_job_id,
        )
        status = resp["ingestionJob"]["status"]
        print(f"  Status: {status}")
        if status in ("COMPLETE", "FAILED", "STOPPED"):
            return status
        time.sleep(10)

def get_region():
    """Get the current AWS region."""
    session = boto3.session.Session()
    return session.region_name or "us-east-1"

def query_kb(kb_id, question):
    """Query the knowledge base using RetrieveAndGenerate."""
    region = get_region()
    client = boto3.client("bedrock-agent-runtime", region_name=region)
    resp = client.retrieve_and_generate(
        input={"text": question},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": kb_id,
                "modelArn": f"arn:aws:bedrock:{region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
            },
        },
    )
    return resp["output"]["text"]

def main():
    if len(sys.argv) < 3:
        print("Usage: python sync-and-query.py <knowledge-base-id> <data-source-id>")
        sys.exit(1)

    kb_id = sys.argv[1]
    ds_id = sys.argv[2]

    bedrock_agent = boto3.client("bedrock-agent")

    # 1. Start ingestion (sync)
    print(f"Starting ingestion for KB={kb_id}, DS={ds_id}...")
    sync_resp = bedrock_agent.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=ds_id,
    )
    job_id = sync_resp["ingestionJob"]["ingestionJobId"]
    print(f"Ingestion job started: {job_id}")

    status = wait_for_sync(bedrock_agent, kb_id, ds_id, job_id)
    if status != "COMPLETE":
        print(f"Ingestion failed with status: {status}")
        sys.exit(1)

    print("\nIngestion complete. Running test queries...\n")

    # 2. Sample queries — answers can ONLY come from the story
    questions = [
        "How many fingers did Elsworth Vane have and how were they distributed?",
        "What was the name of the three-legged cat and what was its special ability?",
        "What was Madame Fisk's submarine called and what powered it?",
        "How fast could the albino squirrels of the postal service travel?",
        "What was the motto carved above Elsworth's workshop door?",
        "How much was the Paradox Pendulum worth in Whisper Coins after modification?",
        "What are the 'flavors of time' displayed by the Paradox Pendulum?",
    ]

    for q in questions:
        print(f"Q: {q}")
        try:
            answer = query_kb(kb_id, q)
            print(f"A: {answer}\n")
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()
