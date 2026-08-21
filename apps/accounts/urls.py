from django.urls import path

from . import views

app_name = 'accounts'
urlpatterns = [
    path('login', views.login, name='auth-login'),
    path('wechat-web/session', views.wechat_web_session, name='wechat-web-session'),
    path('wechat-web/callback', views.wechat_web_callback, name='wechat-web-callback'),
    path('wechat-web/binding-session', views.wechat_web_binding_session, name='wechat-web-binding-session'),
    path('wechat-web/binding-status', views.wechat_web_binding_status, name='wechat-web-binding-status'),
    path('wechat-web/binding-qrcode', views.wechat_web_binding_qrcode, name='wechat-web-binding-qrcode'),
    path('wechat-web/binding-phone', views.wechat_web_binding_phone, name='wechat-web-binding-phone'),
    path('wechat-web/binding-complete', views.wechat_web_binding_complete, name='wechat-web-binding-complete'),
    path('logout', views.logout, name='auth-logout'),
    path('refresh', views.refresh_token_view, name='auth-refresh'),
    path('switch-role', views.switch_role, name='auth-switch-role'),
    path('send-code', views.send_verify_code, name='auth-send-code'),
    path('profile/me', views.profile_me, name='auth-profile'),
]
