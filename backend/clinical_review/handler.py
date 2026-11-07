"""PUBLIC SYNTHETIC DEMO ONLY. No authentication or real medical data."""
import base64
import json
import logging
import uuid
from backend.clinical_review import store
from backend.clinical_review.workflow import case_graph

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
HEADERS = {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}

def reply(status, payload):
    return {'statusCode': status, 'headers': HEADERS, 'body': json.dumps(payload, default=str)}

def body_from(event):
    raw = event.get('body') or '{}'
    if event.get('isBase64Encoded'):
        raw = base64.b64decode(raw).decode('utf-8')
    obj = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(obj, dict):
        raise ValueError('Expected JSON object')
    return obj

def handler(event, context):
    method = event.get('httpMethod', '')
    path = (event.get('path') or '').rstrip('/')
    parts = path.strip('/').split('/')
    try:
        if method == 'POST' and path == '/cases':
            body = body_from(event)
            question = body.get('question')
            if not isinstance(question, str) or not 10 <= len(question.strip()) <= 3000:
                return reply(400, {'error': 'Question must be 10–3000 characters'})
            if body.get('synthetic_only') is not True:
                return reply(400, {'error': 'Confirm synthetic_only=true; real patient information is not permitted'})
            state = case_graph.invoke({'question': question.strip()})
            case_id = str(uuid.uuid4())
            record = {
                'case_id': case_id,
                'question': question.strip(),
                'draft_answer': state['answer'],
                'sources': state.get('sources', []),
                'emergency_warning': bool(state.get('emergency_warning')),
                'status': 'PENDING_REVIEW',
                'created_at': store.now(),
                'version': 1,
            }
            store.create_case(record)
            return reply(202, {
                'case_id': case_id, 'status': 'PENDING_REVIEW',
                'draft_answer': record['draft_answer'], 'sources': record['sources'],
                'emergency_warning': record['emergency_warning'],
                'safety_message': 'Seek emergency care immediately for dangerous symptoms; do not wait for demo review.',
            })
        if method == 'GET' and path == '/doctor/cases':
            records = store.pending_cases()
            return reply(200, {'cases': [
                {'case_id': c['case_id'], 'created_at': c['created_at'], 'status': c['status'], 'version': c['version']}
                for c in records
            ]})
        if method == 'GET' and len(parts) == 2 and parts[0] == 'cases':
            record = store.get_case(parts[1])
            if not record:
                return reply(404, {'error': 'Case not found'})
            # Public demo: anyone with a case ID can view the full synthetic record.
            return reply(200, record)
        if method == 'POST' and len(parts) == 3 and parts[:2] == ['doctor', 'cases']:
            body = body_from(event)
            decision = body.get('decision')
            version = body.get('version')
            reviewed = body.get('approved_text', '')
            if decision not in ('approve', 'reject') or type(version) is not int:
                return reply(400, {'error': 'decision (approve/reject) and integer version required'})
            if decision == 'approve' and (not isinstance(reviewed, str) or not 10 <= len(reviewed.strip()) <= 20000):
                return reply(400, {'error': 'Approved text must be 10–20000 characters'})
            record = store.decide(parts[2], version, decision, 'PUBLIC_DEMO', reviewed.strip() if isinstance(reviewed, str) else '')
            if record is None:
                return reply(409, {'error': 'Case already reviewed or version changed'})
            return reply(200, {'case_id': record['case_id'], 'status': record['status'], 'reviewed_at': record['reviewed_at']})
        return reply(404, {'error': 'Route not found'})
    except (ValueError, json.JSONDecodeError):
        return reply(400, {'error': 'Invalid JSON request'})
    except Exception:
        log.exception('Public synthetic demo case API failed')
        return reply(500, {'error': 'Request failed; inspect clinical review Lambda logs'})
