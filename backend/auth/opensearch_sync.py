import json,os
import boto3,requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from .store import public,list_users

ENDPOINT=os.environ['PHARMACARE_OPENSEARCH_ENDPOINT'].rstrip('/')
INDEX='pharmacare-users'
def request(method,path,payload=None):
    url=ENDPOINT+path
    body=json.dumps(payload,separators=(',',':')).encode() if payload is not None else b''
    headers={'Content-Type':'application/json'}
    req=AWSRequest(method=method,url=url,data=body,headers=headers)
    creds=boto3.Session().get_credentials().get_frozen_credentials()
    SigV4Auth(creds,'es',os.environ.get('AWS_REGION','ap-southeast-2')).add_auth(req)
    r=requests.request(method,url,data=body,headers=dict(req.headers),timeout=15)
    if r.status_code>=400:raise RuntimeError(f'OpenSearch HTTP {r.status_code}: {r.text[:300]}')
    return r.json() if r.content else {}

def ensure_index():
    # Explicit mapping avoids accidentally indexing credentials.
    try:
        request('PUT','/'+INDEX,{'mappings':{'dynamic':'strict','properties':{'user_id':{'type':'keyword'},'username':{'type':'keyword'},'full_name':{'type':'text'},'email':{'type':'keyword'},'role':{'type':'keyword'},'active':{'type':'boolean'},'created_at':{'type':'date'},'updated_at':{'type':'date'}}}})
    except RuntimeError as exc:
        if 'resource_already_exists_exception' not in str(exc):raise

def index_user(user):
    ensure_index()
    return request('PUT','/'+INDEX+'/_doc/'+user['user_id'],public(user))

def rebuild():
    # Full replace clears stale OpenSearch profiles; DynamoDB remains untouched.
    try:request('DELETE','/'+INDEX)
    except RuntimeError as exc:
        if 'index_not_found_exception' not in str(exc):raise
    ensure_index()
    users=list_users(limit=100000)
    for user in users:index_user(user)
    request('POST','/'+INDEX+'/_refresh')
    return {'indexed':len(users)}
