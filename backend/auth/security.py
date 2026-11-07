import base64, hashlib, hmac, json, os, secrets, time
import boto3

_secret_cache = None

def secret():
    global _secret_cache
    if _secret_cache is None:
        value = boto3.client('secretsmanager').get_secret_value(SecretId=os.environ['PHARMACARE_SESSION_SECRET_ARN'])['SecretString']
        _secret_cache = value.encode()
    return _secret_cache

def encode(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def decode(s): return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))

def hash_password(password):
    if len(password) < 12 or len(password) > 128: raise ValueError('Password must be 12-128 characters')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000)
    return 'pbkdf2_sha256$600000$'+encode(salt)+'$'+encode(digest)

def check_password(password,stored):
    try:
        alg, rounds, salt, digest = stored.split('$')
        if alg != 'pbkdf2_sha256' or int(rounds)>1000000: return False
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),decode(salt),int(rounds))
        return hmac.compare_digest(actual,decode(digest))
    except (ValueError,TypeError): return False

def issue_token(user):
    now=int(time.time())
    header=encode(json.dumps({'alg':'HS256','typ':'JWT'},separators=(',',':')).encode())
    payload=encode(json.dumps({'sub':user['user_id'],'iat':now,'exp':now+3600,'ver':int(user.get('session_version',1)),'iss':'pharmacare-ai'},separators=(',',':')).encode())
    data=(header+'.'+payload).encode()
    return header+'.'+payload+'.'+encode(hmac.new(secret(),data,hashlib.sha256).digest())

def verify_token(token):
    try:
        a,b,c=token.split('.')
        if len(token)>4096: return None
        if not hmac.compare_digest(hmac.new(secret(),(a+'.'+b).encode(),hashlib.sha256).digest(),decode(c)):return None
        if json.loads(decode(a))!={'alg':'HS256','typ':'JWT'}:return None
        claims=json.loads(decode(b))
        now=int(time.time())
        if claims.get('iss')!='pharmacare-ai' or not now-30<=claims.get('iat',0)<=now+30 or not now<claims.get('exp',0)<=now+3600:return None
        return claims
    except (ValueError,TypeError,KeyError,UnicodeDecodeError):return None
