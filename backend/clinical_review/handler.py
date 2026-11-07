"""Authenticated case intake, doctor review and patient report API (REST API v1)."""
import json
import logging
import uuid
from backend.clinical_review import store
from backend.clinical_review.workflow import case_graph

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

HEADERS = {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}

def reply(code, body):
    return {'statusCode': code, 'headers': HEADERS, 'body': json.dumps(body, default=str)}

def parse_body(event):
    raw = event.get('body') or '{}'
    if event.get('isBase64Encoded'):
        import base64
        raw = base64.b64decode(raw).decode('utf-8')
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict):
        raise ValueError('JSON object required')
    return value

def identity(event):
    from backend.auth.handler import identity as authenticate
    user = authenticate(event)
    if not user:
        return None, set()
    return user['user_id'], {user['role']}

def handler(event, context):
    try:
        user_id, groups = identity(event)
        if not user_id:
            return reply(401, {'error': 'Authentication required'})
        method = event.get('httpMethod', '')
        path = (event.get('path') or '').rstrip('/')
        if method == 'POST' and path == '/cases':
            if 'patient' not in groups:
                return reply(403, {'error': 'Patient role required'})
            body = parse_body(event)
            question = body.get('question', '')
            if not isinstance(question, str) or not 10 <= len(question.strip()) <= 3000:
                return reply(400, {'error': 'Question must be 10–3000 characters'})
            state = case_graph.invoke({'question': question.strip()})
            case_id = str(uuid.uuid4())
            record = {'case_id': case_id, 'patient_id': user_id, 'question': question.strip(), 'draft_answer': state['answer'], 'sources': state.get('sources', []), 'emergency_warning': bool(state.get('emergency_warning')), 'status': 'PENDING_REVIEW', 'created_at': store.now(), 'version': 1}
            store.create_case(record)
            return reply(202, {'case_id': case_id, 'status': 'PENDING_REVIEW', 'emergency_warning': record['emergency_warning'], 'safety_message': 'If symptoms are severe, sudden, or potentially life-threatening, seek emergency medical help immediately. Do not wait for doctor review.'})
        if method == 'GET' and path == '/doctor/cases':
            if 'doctor' not in groups:
                return reply(403, {'error': 'Doctor role required'})
            records = store.pending_cases()
            return reply(200, {'cases': [{'case_id': c['case_id'], 'created_at': c['created_at'], 'status': c['status'], 'version': c['version']} for c in records]})
        parts = path.strip('/').split('/')
        if len(parts) == 2 and parts[0] == 'cases' and method == 'GET':
            record = store.get_case(parts[1])
            if not record:
                return reply(404, {'error': 'Case not found'})
            is_doctor = 'doctor' in groups
            if not is_doctor and record['patient_id'] != user_id:
                return reply(403, {'error': 'Access denied'})
            if not is_doctor:
                # No unapproved assessment is ever exposed to the patient.
                return reply(200, {'case_id': record['case_id'], 'status': record['status'], 'created_at': record['created_at'], 'emergency_warning': record.get('emergency_warning', False), 'approved_text': record.get('approved_text', '') if record['status'] == 'APPROVED' else '', 'sources': record.get('sources', []) if record['status'] == 'APPROVED' else []})
            return reply(200, record)
        if len(parts) == 3 and parts[0] == 'doctor' and parts[1] == 'cases' and method == 'POST':
            if 'doctor' not in groups:
                return reply(403, {'error': 'Doctor role required'})
            body = parse_body(event)
            decision = body.get('decision')
            approved_text = body.get('approved_text', '')
            version = body.get('version')
            if decision not in ('approve', 'reject') or type(version) is not int:
                return reply(400, {'error': 'Valid decision and integer version required'})
            if decision == 'approve' and (not isinstance(approved_text, str) or not 10 <= len(approved_text.strip()) <= 20000):
                return reply(400, {'error': 'Reviewed text must be 10–20000 characters'})
            record = store.decide(parts[2], version, decision, user_id, approved_text.strip() if isinstance(approved_text, str) else '')
            if not record:
                return reply(409, {'error': 'Case already reviewed or version changed'})
            return reply(200, {'case_id': record['case_id'], 'status': record['status'], 'reviewed_at': record['reviewed_at']})
        return reply(404, {'error': 'Route not found'})
    except (ValueError, json.JSONDecodeError):
        return reply(400, {'error': 'Invalid request'})
    except Exception:
        logger.exception('Clinical review request failed')
        return reply(500, {'error': 'Unable to process request'})
