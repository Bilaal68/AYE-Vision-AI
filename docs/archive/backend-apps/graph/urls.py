from django.urls import path
from .views import GraphDataView

urlpatterns = [
    path('', GraphDataView.as_view(), name='graph-data'),
]
