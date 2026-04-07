"""
Bedrock Knowledge Base — 数据同步 + 多语言查询测试

自动完成以下步骤：
  1. 自动发现 Data Source ID
  2. 触发数据摄取（Ingestion）
  3. 等待 AOSS 索引刷新
  4. 运行英文/中文/德文 + 跨语言查询测试

用法：
  python scripts/sync-and-query.py <knowledge-base-id>

前置条件：
  pip install boto3
  AWS CLI 已配置凭证和区域
"""

import sys
import time
import boto3


def get_region():
    session = boto3.session.Session()
    return session.region_name or "us-east-1"


def discover_data_source(kb_id, region):
    """自动发现知识库关联的第一个 Data Source ID。"""
    client = boto3.client("bedrock-agent", region_name=region)
    resp = client.list_data_sources(knowledgeBaseId=kb_id)
    sources = resp.get("dataSourceSummaries", [])
    if not sources:
        print("Error: No data sources found for this knowledge base.")
        sys.exit(1)
    ds_id = sources[0]["dataSourceId"]
    print(f"Discovered Data Source: {ds_id}")
    return ds_id


def sync_data_source(kb_id, ds_id, region):
    """触发数据摄取并等待完成。"""
    client = boto3.client("bedrock-agent", region_name=region)
    print(f"\n[Step 1] Starting ingestion for KB={kb_id}, DS={ds_id}...")
    resp = client.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)
    job_id = resp["ingestionJob"]["ingestionJobId"]
    print(f"  Ingestion job: {job_id}")

    while True:
        r = client.get_ingestion_job(
            knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id
        )
        job = r["ingestionJob"]
        status = job["status"]
        print(f"  Status: {status}")
        if status == "COMPLETE":
            stats = job.get("statistics", {})
            print(f"  Documents scanned: {stats.get('numberOfDocumentsScanned', '?')}")
            print(f"  Documents indexed: {stats.get('numberOfNewDocumentsIndexed', '?')}")
            print(f"  Documents failed:  {stats.get('numberOfDocumentsFailed', '?')}")
            return
        if status in ("FAILED", "STOPPED"):
            print(f"  Ingestion failed: {status}")
            sys.exit(1)
        time.sleep(10)


def wait_for_index_refresh(kb_id, region, max_wait=60):
    """等待 AOSS 索引刷新，确保数据可被检索。"""
    print(f"\n[Step 2] Waiting for AOSS index refresh (up to {max_wait}s)...")
    client = boto3.client("bedrock-agent-runtime", region_name=region)
    start = time.time()
    while time.time() - start < max_wait:
        resp = client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": "test"},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 1}},
        )
        if resp.get("retrievalResults"):
            print("  Index is ready.")
            return
        time.sleep(5)
    print("  Warning: Index may not be fully refreshed yet, proceeding anyway.")


def query_kb(client, kb_id, question, model_arn):
    """使用 RetrieveAndGenerate API 查询知识库。"""
    resp = client.retrieve_and_generate(
        input={"text": question},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": kb_id,
                "modelArn": model_arn,
            },
        },
    )
    return resp["output"]["text"]


def run_tests(kb_id, region):
    """运行多语言查询测试。"""
    client = boto3.client("bedrock-agent-runtime", region_name=region)
    model_arn = f"arn:aws:bedrock:{region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"

    test_cases = [
        # --- English (The Clockmaker of Nowhere) ---
        ("EN→EN", "What was the name of the three-legged cat and what was its special ability?"),
        ("EN→EN", "What powered Madame Fisk's submarine?"),
        ("EN→EN", "How many fingers did Elsworth Vane have?"),
        # --- 中文 (重庆面条巫师) ---
        ("ZH→ZH", "蒋铜锅的面条工作室由什么动物守卫？它有什么特殊能力？"),
        ("ZH→ZH", "量子牛肉面的售价是多少雾币？"),
        ("ZH→ZH", "醋婆婆的飞行火锅店叫什么名字？靠什么驱动？"),
        ("ZH→ZH", "面条工作室的座右铭是什么？"),
        # --- Deutsch (Der Wolkenschmied von Heidelberg) ---
        ("DE→DE", "Wie hieß der zweischwänzige Dachs und wie viele Nasen hatte er?"),
        ("DE→DE", "Wie viel kostete die Donnerharfe in Nebelgroschen?"),
        ("DE→DE", "Wie hieß das fliegende Brauhaus von Frau Blitzschlag und was trieb es an?"),
        ("DE→DE", "Was war das Motto über der Werkstatttür von Balthasar?"),
        # --- Cross-language ---
        ("ZH→EN", "Elsworth Vane有多少根手指？"),
        ("EN→ZH", "What animal guards the noodle workshop and what is its special ability?"),
        ("EN→DE", "What is the motto above Balthasar's workshop door?"),
    ]

    print(f"\n[Step 3] Running {len(test_cases)} test queries...\n")
    print("=" * 80)

    passed = 0
    failed = 0
    for tag, question in test_cases:
        print(f"[{tag}] Q: {question}")
        try:
            answer = query_kb(client, kb_id, question, model_arn)
            is_fail = "unable to assist" in answer.lower() or "sorry" in answer.lower()[:20]
            status_icon = "❌" if is_fail else "✅"
            print(f"  {status_icon} A: {answer}")
            if is_fail:
                failed += 1
            else:
                passed += 1
        except Exception as e:
            print(f"  ❌ Error: {e}")
            failed += 1
        print()

    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed, {len(test_cases)} total")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/sync-and-query.py <knowledge-base-id>")
        print()
        print("The Data Source ID is auto-discovered.")
        print("Set AWS_DEFAULT_REGION if needed (e.g. export AWS_DEFAULT_REGION=ap-southeast-1)")
        sys.exit(1)

    kb_id = sys.argv[1]
    region = get_region()
    print(f"Knowledge Base: {kb_id}")
    print(f"Region: {region}")

    ds_id = discover_data_source(kb_id, region)
    sync_data_source(kb_id, ds_id, region)
    wait_for_index_refresh(kb_id, region)
    run_tests(kb_id, region)


if __name__ == "__main__":
    main()
