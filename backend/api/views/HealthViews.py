
from django.db import connection

from rest_framework.views import APIView
from rest_framework.response import Response

from .common import error


class HealthView(APIView):
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            return Response({
                "status": "ok",
                "database": "connected",
            })

        except Exception:
            return error("Database unavailable.", 503)
