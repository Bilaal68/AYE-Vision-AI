from rest_framework.views import APIView
from rest_framework.response import Response

class IncidentListView(APIView):
    def get(self, request):
        return Response({"message": "Incidents API placeholder", "incidents": []})
