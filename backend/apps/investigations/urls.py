from django.urls import path
from .views import InvestigationListView

urlpatterns = [
    path('', InvestigationListView.as_view(), name='investigation-list'),
]
