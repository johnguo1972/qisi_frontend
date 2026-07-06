from django.urls import path
from . import views

app_name = 'wrongbook'
urlpatterns = [
    path('', views.wrongbook_list, name='wrongbook-list'),
    path('<int:item_id>', views.wrongbook_detail, name='wrongbook-detail'),
    path('<int:item_id>/variants', views.wrongbook_variants, name='wrongbook-variants'),
    path('mastery', views.mastery_list, name='mastery-list'),
]
