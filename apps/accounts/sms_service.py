"""Tencent Cloud SMS sending service."""
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.sms.v20210111.sms_client import SmsClient
from tencentcloud.sms.v20210111 import models
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class TencentSMSService:
    """Tencent Cloud SMS sender."""

    def __init__(self):
        self.secret_id = settings.TENCENT_SMS_SECRET_ID
        self.secret_key = settings.TENCENT_SMS_SECRET_KEY
        self.sdk_app_id = settings.TENCENT_SMS_SDK_APP_ID
        self.sign_name = settings.TENCENT_SMS_SIGN_NAME
        self.region = settings.TENCENT_SMS_REGION

        cred = credential.Credential(self.secret_id, self.secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "sms.tencentcloudapi.com"

        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile

        self.client = SmsClient(cred, self.region, client_profile)

    def send_verify_code(self, phone_number: str, verify_code: str, scene: str = 'login') -> dict:
        """Send verification code SMS.

        Args:
            phone_number: 手机号，如 "13800138000"
            verify_code: 6位验证码
            scene: 'login' 或 'register'，决定使用哪个模板

        Returns:
            dict with 'success', 'serial_no', 'code', 'message'
        """
        # 选择模板
        if scene == 'register':
            template_id = settings.TENCENT_SMS_REGISTER_TEMPLATE_ID
        else:
            template_id = settings.TENCENT_SMS_LOGIN_TEMPLATE_ID

        req = models.SendSmsRequest()
        req.SmsSdkAppId = self.sdk_app_id
        req.SignName = self.sign_name
        req.TemplateId = template_id
        # 手机号需要加国际码前缀
        req.PhoneNumberSet = [f"+86{phone_number}"]
        req.TemplateParamSet = [verify_code]

        try:
            resp = self.client.SendSms(req)
            status = resp.SendStatusSet[0] if resp.SendStatusSet else None
            if status and status.Code == "Ok":
                logger.info(f"SMS sent successfully to {phone_number}, serial: {status.SerialNo}")
                return {
                    'success': True,
                    'serial_no': status.SerialNo,
                    'code': status.Code,
                    'message': status.Message,
                }
            else:
                error_msg = f"SMS send failed: {status.Code} - {status.Message}" if status else "No status returned"
                logger.error(error_msg)
                return {
                    'success': False,
                    'serial_no': '',
                    'code': status.Code if status else 'Unknown',
                    'message': status.Message if status else 'No status',
                }
        except TencentCloudSDKException as err:
            logger.error(f"TencentCloud SDK error: {err.code}: {err.message}")
            return {
                'success': False,
                'serial_no': '',
                'code': err.code,
                'message': err.message,
            }
