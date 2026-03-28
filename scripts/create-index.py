"""
Creates the vector index in OpenSearch Serverless.
Run AFTER cdk deploy and BEFORE syncing the data source.

Usage:
  python scripts/create-index.py <collection-endpoint>

The collection endpoint is printed in the CloudFormation outputs or
can be found in the OpenSearch Serverless console.
"""

import sys
import json
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

def main():
    if len(sys.argv) < 2:
        print("Usage: python create-index.py <collection-endpoint>")
        print("  e.g. python create-index.py https://abc123.us-east-1.aoss.amazonaws.com")
        sys.exit(1)

    host = sys.argv[1].replace("https://", "")
    region = boto3.session.Session().region_name or "us-east-1"
    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, region, "aoss")

    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=60,
    )

    index_name = "bedrock-kb-index"
    index_body = {
        "settings": {
            "index.knn": True,
        },
        "mappings": {
            "properties": {
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "engine": "faiss",
                        "name": "hnsw",
                    },
                },
                "text": {"type": "text"},
                "metadata": {"type": "text"},
            }
        },
    }

    if client.indices.exists(index=index_name):
        print(f"Index '{index_name}' already exists. Skipping creation.")
    else:
        resp = client.indices.create(index=index_name, body=index_body)
        print(f"Index created: {json.dumps(resp, indent=2)}")

if __name__ == "__main__":
    main()
