from rest_framework.views import APIView
from rest_framework.response import Response

class InvestigationListView(APIView):
    def get(self, request):
        return Response({"message": "Investigations API placeholder", "investigations": []})
