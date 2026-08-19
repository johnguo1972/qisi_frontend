from django.urls import path

from . import views

app_name = 'accounts'
urlpatterns = [
    path('login', views.login, name='auth-login'),
    path('wechat-web/binding-session', views.wechat_web_binding_session, name='wechat-web-binding-session'),
    path('wechat-web/binding-status', views.wechat_web_binding_status, name='wechat-web-binding-status'),
    path('wechat-web/binding-complete', views.wechat_web_binding_complete, name='wechat-web-binding-complete'),
    path('logout', views.logout, name='auth-logout'),
    path('refresh', views.refresh_token_view, name='auth-refresh'),
    path('switch-role', views.switch_role, name='auth-switch-role'),
    path('send-code', views.send_verify_code, name='auth-send-code'),
    path('profile/me', views.profile_me, name='auth-profile'),
]
