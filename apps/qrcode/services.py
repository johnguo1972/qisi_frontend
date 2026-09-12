import io
import secrets
import string
import time
from dataclasses import dataclass
from datetime import timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import MissionShortCode, StudentClassShortCode

SHORT_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
STUDENT_ALPHABET = SHORT_ALPHABET
WECHAT_ACCESS_TOKEN_CACHE_SECONDS = 7100
WECHAT_INVALID_TOKEN_ERROR_CODES = {40001, 40014, 42001}


def _wechat_access_token(appid, secret, *, force_refresh=False):
    """Reuse the Mini Program access token instead of requesting one per QR."""
    cache_key = f'wechat:mp:access-token:{appid}'
    if not force_refresh:
        try:
            cached_token = cache.get(cache_key)
        except Exception:
            cached_token = None
        if isinstance(cached_token, str) and cached_token:
            return cached_token

    try:
        token_result = requests.get(
            'https://api.weixin.qq.com/cgi-bin/token',
            params={'grant_type': 'client_credential', 'appid': appid, 'secret': secret},
            timeout=8,
        ).json()
    except (requests.RequestException, ValueError) as error:
        raise RuntimeError('wechat access_token request failed') from error
    access_token = token_result.get('access_token')
    if not access_token:
        raise RuntimeError(token_result.get('errmsg', 'wechat access_token request failed'))
    try:
        cache.set(
            cache_key,
            access_token,
            timeout=min(
                WECHAT_ACCESS_TOKEN_CACHE_SECONDS,
                max(60, int(token_result.get('expires_in', 7200)) - 60),
            ),
        )
    except Exception:
        # QR generation must remain available if the optional cache is down.
        pass
    return access_token


def _unique_code(length, alphabet):
    for _ in range(5):
        value = ''.join(secrets.choice(alphabet) for _ in range(length))
        if not MissionShortCode.objects.filter(short_code=value).exists() and not StudentClassShortCode.objects.filter(short_code=value).exists():
            return value
    raise RuntimeError('短码生成失败，请稍后重试')


def ensure_mission_short_code(mission, class_obj=None):
    """Return an idempotent code for one mission/class publication."""
    if class_obj is None:
        class_obj = mission.class_obj
    expires_at = mission.end_at
    code, created = MissionShortCode.objects.get_or_create(
        mission=mission,
        class_obj=class_obj,
        defaults={
            'short_code': _unique_code(6, SHORT_ALPHABET),
            'expires_at': expires_at,
            'payload_json': {'type': 'mission', 'mission_id': str(mission.id), 'class_id': str(getattr(class_obj, 'id', class_obj or ''))},
        },
    )
    if not created and expires_at != code.expires_at:
        code.expires_at = expires_at
        code.save(update_fields=['expires_at', 'updated_at'])
    return code


def ensure_mission_short_codes(mission):
    """Create codes for every active class, with legacy fallback."""
    assignments = list(mission.class_assignments.filter(status='active').select_related('class_obj'))
    if not assignments:
        return [ensure_mission_short_code(mission)]
    return [ensure_mission_short_code(mission, item.class_obj) for item in assignments]


def ensure_student_short_code(student, class_obj):
    code, _ = StudentClassShortCode.objects.get_or_create(
        student=student,
        class_obj=class_obj,
        defaults={'short_code': _unique_code(8, STUDENT_ALPHABET)},
    )
    return code


def qr_png(value, size=300):
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M

    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M, box_size=max(4, int(size / 75)), border=4)
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(fill_color='black', back_color='white')
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def mission_qr_url(code):
    base = getattr(settings, 'PUBLIC_WEB_URL', '').rstrip('/')
    return f'{base}/hw/{code}' if base else f'/hw/{code}'


def paper_qr_url(student_code, mission_code, page_no=1):
    base = getattr(settings, 'PUBLIC_WEB_URL', '').rstrip('/')
    path = f'/paper/{student_code}/{mission_code}/p{int(page_no)}'
    return f'{base}{path}' if base else path


def analyze_image_blur(file_obj):
    """Return a reproducible 0-100 sharpness score and blur flag."""
    try:
        from PIL import Image, ImageFilter, ImageStat
        file_obj.seek(0)
        image = Image.open(file_obj).convert('L')
        image.thumbnail((1200, 1200))
        edges = image.filter(ImageFilter.FIND_EDGES)
        if edges.width > 20 and edges.height > 20:
            margin_x, margin_y = int(edges.width * 0.08), int(edges.height * 0.08)
            edges = edges.crop((margin_x, margin_y, edges.width - margin_x, edges.height - margin_y))
        variance = ImageStat.Stat(edges).var[0]
        score = max(0.0, min(100.0, variance * 2.5))
        file_obj.seek(0)
        return round(score, 2), score < 50.0
    except Exception:
        file_obj.seek(0)
        return None, False


@dataclass(frozen=True)
class WechatCodeImage:
    content: bytes
    content_type: str


def wxacode_image(
    scene,
    page='pages/student/scan-entry',
    width=430,
    check_path=False,
    env_version='release',
):
    """Generate a real unlimited mini-program code with its actual MIME type."""
    env_version = str(env_version).strip().lower()
    if env_version not in {'release', 'trial', 'develop'}:
        raise RuntimeError('invalid miniprogram env_version')
    appid = getattr(settings, 'WECHAT_MP_APPID', '')
    secret = getattr(settings, 'WECHAT_MP_APPSECRET', '')
    if not appid or not secret:
        raise RuntimeError('微信小程序 AppID/AppSecret 未配置')
    request_body = {
        'scene': str(scene)[:32],
        'page': page,
        'check_path': bool(check_path),
        'env_version': env_version,
        'width': width,
    }
    for attempt in range(2):
        access_token = _wechat_access_token(
            appid, secret, force_refresh=attempt == 1
        )
        response = requests.post(
            'https://api.weixin.qq.com/wxa/getwxacodeunlimit',
            params={'access_token': access_token},
            json=request_body,
            timeout=15,
        )
        content_type = response.headers.get('Content-Type', '').split(';', 1)[0].lower()
        if content_type in {'image/jpeg', 'image/png'}:
            return WechatCodeImage(content=response.content, content_type=content_type)

        try:
            error_payload = response.json()
        except ValueError:
            error_payload = {}
        error_code = error_payload.get('errcode')
        if attempt == 0 and error_code in WECHAT_INVALID_TOKEN_ERROR_CODES:
            # A deployment may retain a token issued before an AppSecret change,
            # or WeChat may revoke a token early. Fetch a fresh one once.
            continue
        message = error_payload.get('errmsg', '生成微信小程序码失败')
        raise RuntimeError(message)


def wxacode_png(
    scene,
    page='pages/student/scan-entry',
    width=430,
    check_path=False,
    env_version='release',
):
    """Compatibility wrapper for legacy callers that only need bytes."""
    return wxacode_image(
        scene=scene,
        page=page,
        width=width,
        check_path=check_path,
        env_version=env_version,
    ).content


def wechat_url_link(scene, path='pages/student/scan-entry'):
    """Generate a short-lived WeChat URL Link for an H5 page."""
    import requests
    appid = getattr(settings, 'WECHAT_MP_APPID', '')
    secret = getattr(settings, 'WECHAT_MP_APPSECRET', '')
    if not appid or not secret:
        raise RuntimeError('微信小程序 AppID/AppSecret 未配置')
    token_result = requests.get('https://api.weixin.qq.com/cgi-bin/token', params={'grant_type': 'client_credential', 'appid': appid, 'secret': secret}, timeout=8).json()
    token = token_result.get('access_token')
    if not token:
        raise RuntimeError(token_result.get('errmsg', '获取微信 access_token 失败'))
    response = requests.post('https://api.weixin.qq.com/wxa/generate_urllink', params={'access_token': token}, json={'path': path, 'query': f'scene={scene}', 'expire_type': 1, 'expire_time': int(time.time()) + 7200}, timeout=15)
    data = response.json()
    if data.get('errcode') or not data.get('url_link'):
        raise RuntimeError(data.get('errmsg', '生成微信 URL Link 失败'))
    return data['url_link']


def cache_wechat_pending(appid, openid, unionid=''):
    token = secrets.token_urlsafe(32)
    cache.set(f'wechat_pending:{token}', {'appid': appid, 'openid': openid, 'unionid': unionid}, timeout=600)
    return token
