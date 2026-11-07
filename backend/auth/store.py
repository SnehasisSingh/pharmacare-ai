import os,uuid
from datetime import datetime,timezone
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeSerializer
from .security import hash_password,check_password

table=boto3.resource('dynamodb').Table(os.environ['PHARMACARE_USERS_TABLE'])
def now():return datetime.now(timezone.utc).isoformat()
def username_key(name):return 'USERNAME#'+name.strip().lower()
def user_key(uid):return 'USER#'+uid

def get_by_username(name):
    if not isinstance(name,str) or not name.strip():return None
    pointer=table.get_item(Key={'pk':username_key(name),'sk':'LOOKUP'},ConsistentRead=True).get('Item')
    return get_user(pointer['user_id']) if pointer else None

def get_user(uid):return table.get_item(Key={'pk':user_key(uid),'sk':'PROFILE'},ConsistentRead=True).get('Item')
def public(u):return {k:u.get(k) for k in ('user_id','username','full_name','email','role','active','created_at','updated_at')}

def create(username,password,full_name,email,role):
    username=username.strip().lower()
    if not (3<=len(username)<=64 and all(c.isalnum() or c in '._-' for c in username)):raise ValueError('Invalid username')
    if role not in ('admin','doctor','patient'):raise ValueError('Invalid role')
    if not (1<=len(full_name.strip())<=120) or len(email)>254:raise ValueError('Invalid profile')
    uid=str(uuid.uuid4());t=now()
    user={'pk':user_key(uid),'sk':'PROFILE','user_id':uid,'username':username,'full_name':full_name.strip(),'email':email.strip(),'role':role,'active':True,'password_hash':hash_password(password),'session_version':1,'created_at':t,'updated_at':t}
    pointer={'pk':username_key(username),'sk':'LOOKUP','user_id':uid}
    boto3.client('dynamodb').transact_write_items(TransactItems=[
        {'Put':{'TableName':table.name,'Item':TypeSerializer().serialize(user)['M'],'ConditionExpression':'attribute_not_exists(pk)'}},
        {'Put':{'TableName':table.name,'Item':TypeSerializer().serialize(pointer)['M'],'ConditionExpression':'attribute_not_exists(pk)'}}])
    return user

def list_users(limit=100):
    # Administrative list. For large datasets replace scan with a role/status GSI and pagination.
    out=[];kwargs={'FilterExpression':'sk = :profile','ExpressionAttributeValues':{':profile':'PROFILE'}}
    while True:
        result=table.scan(**kwargs)
        out.extend(public(u) for u in result.get('Items',[]))
        if 'LastEvaluatedKey' not in result or len(out)>=limit:break
        kwargs['ExclusiveStartKey']=result['LastEvaluatedKey']
    return sorted(out[:limit],key=lambda x:x['username'])

def update(uid,changes):
    allowed={'full_name','email','active','password'}
    if not changes or not set(changes)<=allowed:raise ValueError('Unsupported update')
    if 'full_name' in changes and not (isinstance(changes['full_name'],str) and 1<=len(changes['full_name'].strip())<=120):raise ValueError('Invalid name')
    if 'email' in changes and not (isinstance(changes['email'],str) and len(changes['email'])<=254):raise ValueError('Invalid email')
    if 'active' in changes and type(changes['active']) is not bool:raise ValueError('Invalid active flag')
    vals={':updated':now()}; names={'#updated':'updated_at'};parts=['#updated=:updated']
    for k in ('full_name','email','active'):
        if k in changes:
            names['#'+k]=k;vals[':'+k]=changes[k].strip() if isinstance(changes[k],str) else changes[k];parts.append('#'+k+'=:'+k)
    if 'password' in changes:
        names['#password']='password_hash';vals[':password']=hash_password(changes['password']);parts.append('#password=:password')
    if 'password' in changes or changes.get('active') is False:
        parts.append('session_version=session_version+:one');vals[':one']=1
    try:
        result=table.update_item(Key={'pk':user_key(uid),'sk':'PROFILE'},UpdateExpression='SET '+','.join(parts),ConditionExpression='attribute_exists(pk)',ExpressionAttributeNames=names,ExpressionAttributeValues=vals,ReturnValues='ALL_NEW')
        return result['Attributes']
    except ClientError as e:
        if e.response['Error']['Code']=='ConditionalCheckFailedException':return None
        raise
