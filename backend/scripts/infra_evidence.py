"""Inventario de la infraestructura REAL desplegada (Entregables 2 y 3). Genera docs/evidencias/03-infraestructura.md."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3

REGION = "us-east-2"
STACK = "tripplanner-backend"
TABLE = "tripplanner-main"
out = Path(__file__).resolve().parents[2] / "docs" / "evidencias" / "03-infraestructura.md"

cf = boto3.client("cloudformation", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)
iam = boto3.client("iam", region_name=REGION)
ddb = boto3.client("dynamodb", region_name=REGION)
apigw = boto3.client("apigatewayv2", region_name=REGION)
cog = boto3.client("cognito-idp", region_name=REGION)
cfd = boto3.client("cloudfront", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)
agent = boto3.client("bedrock-agentcore-control", region_name=REGION)
sts = boto3.client("sts")

account = sts.get_caller_identity()["Account"]
outputs = {o["OutputKey"]: o["OutputValue"] for o in cf.describe_stacks(StackName=STACK)["Stacks"][0]["Outputs"]}
lines = [
    "# Evidencia 03 — Infraestructura desplegada (inventario real)",
    "",
    f"- Fecha: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · Cuenta `{account}` · Región `{REGION}`",
    f"- Stack SAM: `{STACK}` · estado `{cf.describe_stacks(StackName=STACK)['Stacks'][0]['StackStatus']}`",
    "",
    "## Salidas del stack",
    "",
    "| Salida | Valor |", "|---|---|",
    *[f"| {k} | `{v}` |" for k, v in sorted(outputs.items())],
    "",
]

# --- DynamoDB
t = ddb.describe_table(TableName=TABLE)["Table"]
counts = {}
for page in ddb.get_paginator("scan").paginate(TableName=TABLE, ProjectionExpression="SK"):
    for item in page["Items"]:
        kind = item["SK"]["S"].split("#")[0]
        counts[kind] = counts.get(kind, 0) + 1
pitr = boto3.client("dynamodb", region_name=REGION).describe_continuous_backups(TableName=TABLE)["ContinuousBackupsDescription"]["PointInTimeRecoveryDescription"]["PointInTimeRecoveryStatus"]
lines += [
    "## DynamoDB (Entregable 3)", "",
    f"- Tabla `{t['TableName']}` · estado **{t['TableStatus']}** · facturación `{t.get('BillingModeSummary', {}).get('BillingMode')}`",
    f"- Ítems actuales (conteo por `Scan` solo para esta evidencia): " + ", ".join(f"{n} `{k}`" for k, n in sorted(counts.items())) + f" — total {sum(counts.values())}",
    f"- Claves: " + ", ".join(f"`{k['AttributeName']}` ({k['KeyType']})" for k in t["KeySchema"]),
    f"- Cifrado en reposo: `{t.get('SSEDescription', {}).get('Status', 'ENABLED (clave propiedad de AWS)')}` · Recuperación a un punto en el tiempo: `{pitr}`",
    "",
]

# --- Lambdas
lines += ["## Funciones Lambda y sus permisos IAM (Entregable 2)", "", "| Función | Handler | Runtime | Memoria | Timeout | Acciones DynamoDB permitidas |", "|---|---|---|---|---|---|"]
for fn in sorted(lam.list_functions()["Functions"], key=lambda f: f["FunctionName"]):
    if not fn["FunctionName"].startswith("tripplanner-"):
        continue
    role = fn["Role"].split("/")[-1]
    actions = set()
    for name in iam.list_role_policies(RoleName=role)["PolicyNames"]:
        doc = iam.get_role_policy(RoleName=role, PolicyName=name)["PolicyDocument"]
        for st in doc["Statement"] if isinstance(doc["Statement"], list) else [doc["Statement"]]:
            for a in ([st["Action"]] if isinstance(st["Action"], str) else st["Action"]):
                if a.startswith("dynamodb:"):
                    actions.add(a.replace("dynamodb:", ""))
    lines.append(f"| `{fn['FunctionName']}` | `{fn['Handler']}` | {fn['Runtime']} | {fn['MemorySize']} MB | {fn['Timeout']} s | {', '.join(sorted(actions)) or '—'} |")
lines.append("")

# --- API Gateway
api_id = outputs["ApiUrl"].split("//")[1].split(".")[0]
api = apigw.get_api(ApiId=api_id)
routes = sorted(r["RouteKey"] + (f"  (auth: {r['AuthorizationType']})") for r in apigw.get_routes(ApiId=api_id)["Items"])
auth = apigw.get_authorizers(ApiId=api_id)["Items"][0]
stage = apigw.get_stage(ApiId=api_id, StageName="$default")
lines += [
    "## API Gateway HTTP (Entregable 2)", "",
    f"- `{api['Name']}` · `{api['ApiEndpoint']}`",
    f"- Autorizador `{auth['AuthorizerType']}`: issuer `{auth['JwtConfiguration']['Issuer']}`, audiencia `{auth['JwtConfiguration']['Audience']}`",
    f"- CORS: orígenes `{api.get('CorsConfiguration', {}).get('AllowOrigins')}`, métodos `{api.get('CorsConfiguration', {}).get('AllowMethods')}`",
    f"- Throttling por defecto: `{stage.get('DefaultRouteSettings')}`",
    "", "Rutas:", "", *[f"- `{r}`" for r in routes], "",
]

# --- Cognito
pool_id = outputs["UserPoolId"]
pool = cog.describe_user_pool(UserPoolId=pool_id)["UserPool"]
lines += [
    "## Cognito", "",
    f"- User Pool `{pool['Name']}` (`{pool_id}`) · usuarios estimados: {pool.get('EstimatedNumberOfUsers')}",
    f"- Política de contraseñas: mínimo {pool['Policies']['PasswordPolicy']['MinimumLength']}, mayúscula/minúscula/número",
    f"- Trigger PreSignUp: `{pool['LambdaConfig'].get('PreSignUp', '').split(':')[-1]}`",
    "",
]

# --- S3 / CloudFront
bucket = outputs["FrontendBucketName"]
pab = s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
objs = s3.list_objects_v2(Bucket=bucket).get("KeyCount")
dist = cfd.get_distribution(Id=outputs["DistributionId"])["Distribution"]
lines += [
    "## Frontend: S3 + CloudFront (Entregable 1)", "",
    f"- Bucket `{bucket}` · objetos: {objs} · bloqueo de acceso público: `{all(pab.values())}`",
    f"- CloudFront `{dist['Id']}` · estado **{dist['Status']}** · URL `https://{dist['DomainName']}`",
    "",
]

# --- AgentCore
lines += ["## Agentes en Amazon Bedrock AgentCore", "", "| Runtime | Protocolo | Estado | Autorización |", "|---|---|---|---|"]
for r in sorted(agent.list_agent_runtimes()["agentRuntimes"], key=lambda r: r["agentRuntimeName"]):
    d = agent.get_agent_runtime(agentRuntimeId=r["agentRuntimeId"])
    proto = d.get("protocolConfiguration", {}).get("serverProtocol") or "HTTP"
    auth_type = "CUSTOM_JWT (Cognito)" if d.get("authorizerConfiguration") else "AWS_IAM"
    lines.append(f"| `{r['agentRuntimeName']}` | {proto} | {d['status']} | {auth_type} |")
lines.append("")
mem = agent.list_memories().get("memories", [])
lines += ["Memorias de AgentCore: " + (", ".join(f"`{m.get('id')}` ({m.get('status')})" for m in mem) or "—"), ""]

out.write_text("\n".join(lines), encoding="utf-8")
print("->", out)
sys.exit(0)
