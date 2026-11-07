import base64,json,logging,os,time
from botocore.exceptions import ClientError
from . import store,security,opensearch_sync
logger=logging.getLogger(__name__)
HEADERS={'Content-Type':'application/json','Cache-Control':'no-store'}
def reply(code,data):return {'statusCode':code,'headers':HEADERS,'body':json.dumps(data)}
def body(event):
    raw=event.get('body') or '{}'
    if event.get('isBase64Encoded'):raw=base64.b64decode(raw)
    val=json.loads(raw)
    if not isinstance(val,dict):raise ValueError('JSON object required')
    return val

def identity(event):
    h={k.lower():v for k,v in (event.get('headers') or {}).items()}
    token=h.get('authorization','')
    if not token.lower().startswith('bearer '):return None
    claims=security.verify_token(token[7:].strip())
    if not claims:return None
    user=store.get_user(claims['sub'])
    if not user or not user.get('active') or user.get('session_version',1)!=claims.get('ver'):return None
    return user

def handler(event,context):
    try:
        method=event.get('httpMethod','');path=(event.get('path') or '').rstrip('/')
        if method=='POST' and path=='/auth/login':
            data=body(event);username=data.get('username','');password=data.get('password','')
            if not isinstance(username,str) or not isinstance(password,str):return reply(400,{'error':'Invalid login'})
            user=store.get_by_username(username)
            # Constant-cost dummy verification for nonexistent users.
            valid=security.check_password(password,user['password_hash'] if user else DUMMY_HASH)
            if not user or not user.get('active') or not valid:return reply(401,{'error':'Invalid credentials'})
            return reply(200,{'token':security.issue_token(user),'expires_in':3600,'user':store.public(user)})
        user=identity(event)
        if not user:return reply(401,{'error':'Login required'})
        if method=='GET' and path=='/auth/me':return reply(200,{'user':store.public(user)})
        if user['role']!='admin':return reply(403,{'error':'Administrator required'})
        if method=='GET' and path=='/admin/users':return reply(200,{'users':store.list_users()})
        if method=='POST' and path=='/admin/users':
            data=body(event)
            if data.get('role') not in ('patient','doctor'):return reply(400,{'error':'Role must be patient or doctor'})
            new=store.create(data['username'],data['password'],data['full_name'],data.get('email',''),data['role'])
            try:opensearch_sync.index_user(new)
            except Exception:logger.exception('OpenSearch sync pending; DynamoDB save succeeded')
            return reply(201,{'user':store.public(new),'message':'Saved to DynamoDB; OpenSearch indexing attempted'})
        parts=path.strip('/').split('/')
        if method=='PATCH' and len(parts)==3 and parts[:2]==['admin','users']:
            data=body(event)
            if 'password' in data and data['password']=='':data.pop('password')
            if parts[2]==user['user_id'] and data.get('active') is False:return reply(400,{'error':'Cannot disable own admin account'})
            changed=store.update(parts[2],data)
            if not changed:return reply(404,{'error':'User not found'})
            try:opensearch_sync.index_user(changed)
            except Exception:logger.exception('OpenSearch sync pending')
            return reply(200,{'user':store.public(changed)})
        if method=='POST' and path=='/admin/opensearch/rebuild':
            return reply(200,opensearch_sync.rebuild())
        return reply(404,{'error':'Not found'})
    except (ValueError, KeyError, TypeError) as exc:
        logger.exception(
            "Auth request failed: %s",
            type(exc).__name__
        )
        return reply(400, {"error": "Invalid request"})
    except ClientError as e:
        if e.response['Error']['Code']=='TransactionCanceledException':return reply(409,{'error':'Username already exists or transaction failed'})
        logger.exception('Auth database error');return reply(500,{'error':'Database error'})
    except Exception:
        logger.exception('Auth API failure');return reply(500,{'error':'Request failed'})

# Precomputed dummy hash: fixed work factor, no secret data.
DUMMY_HASH=security.hash_password('not-a-real-user-password')
