"""One-time admin bootstrap. Run locally with AWS credentials; do not deploy as API."""
import argparse,os,getpass,sys
import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.auth.security import hash_password
from datetime import datetime,timezone
import uuid
p=argparse.ArgumentParser();p.add_argument('--table',default='pharmacare-ai-dev-users-db');p.add_argument('--region',default='ap-southeast-2');p.add_argument('--username',required=True);p.add_argument('--name',required=True);p.add_argument('--email',default='');args=p.parse_args()
username=args.username.strip().lower()
if not (3<=len(username)<=64 and all(c.isalnum() or c in '._-' for c in username)):sys.exit('Invalid username')
pw=getpass.getpass('Admin password (12-128 chars): ')
confirm=getpass.getpass('Repeat password: ')
if pw!=confirm:sys.exit('Passwords do not match')
uid=str(uuid.uuid4());now=datetime.now(timezone.utc).isoformat()
user={'pk':'USER#'+uid,'sk':'PROFILE','user_id':uid,'username':username,'full_name':args.name,'email':args.email,'role':'admin','active':True,'password_hash':hash_password(pw),'session_version':1,'created_at':now,'updated_at':now}
pointer={'pk':'USERNAME#'+username,'sk':'LOOKUP','user_id':uid}
ser=TypeSerializer()
def encode(item):return {k:ser.serialize(v) for k,v in item.items()}
client=boto3.client('dynamodb',region_name=args.region)
try:
 client.transact_write_items(TransactItems=[{'Put':{'TableName':args.table,'Item':encode(user),'ConditionExpression':'attribute_not_exists(pk)'}},{'Put':{'TableName':args.table,'Item':encode(pointer),'ConditionExpression':'attribute_not_exists(pk)'}}])
 print('Admin created in DynamoDB. Log in to admin UI and run Restore OpenSearch.')
except ClientError as exc:sys.exit('Bootstrap failed: '+exc.response['Error']['Code'])
