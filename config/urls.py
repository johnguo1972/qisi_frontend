from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.accounts.views import profile_me
from apps.knowledge.teacher_api_views import knowledge_tree
from apps.study.favorites_views import favorites_list, favorites_add, favorites_remove

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/profile/me', profile_me, name='profile-me'),
    # Institutions must come before /student/ to avoid prefix collision
    path('api/v1/', include('apps.institutions.urls')),
    path('api/v1/', include('apps.review.urls')),  # Review API (before questions)
    path('api/v1/', include('apps.courses.urls')),  # Courses API
    path('api/v1/papers/', include('apps.papers.urls')),  # Papers API
    path('api/v1/questions/', include('apps.study.urls')),
    path('api/v1/missions/', include('apps.missions.urls')),
    path('api/v1/student/', include('apps.study.student_urls')),
    path('api/v1/student/wrong-book/', include('apps.wrongbook.urls')),
    path('api/v1/dicts/', include('apps.study.dict_urls')),
    # Teacher knowledge tree API
    path('api/v1/teacher/knowledge-tree/', knowledge_tree, name='teacher-knowledge-tree'),
    # Teacher favorites
    path('api/v1/teacher/favorites/', favorites_list, name='favorites-list'),
    path('api/v1/teacher/favorites/add/', favorites_add, name='favorites-add'),
    path('api/v1/teacher/favorites/<int:question_id>/', favorites_remove, name='favorites-remove'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
