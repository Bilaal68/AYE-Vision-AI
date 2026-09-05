from django.urls import path
from .views import EntityListView

urlpatterns = [
    path('', EntityListView.as_view(), name='entity-list'),
]
