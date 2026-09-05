from rest_framework.views import APIView
from rest_framework.response import Response

class EventListView(APIView):
    def get(self, request):
        return Response({"message": "Events API placeholder", "events": []})
