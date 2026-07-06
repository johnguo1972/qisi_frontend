from django.urls import path

from . import views

app_name = 'accounts'
urlpatterns = [
    path('login', views.login, name='auth-login'),
    path('logout', views.logout, name='auth-logout'),
    path('refresh', views.refresh_token_view, name='auth-refresh'),
    path('send-code', views.send_verify_code, name='auth-send-code'),
    path('profile/me', views.profile_me, name='auth-profile'),
]
