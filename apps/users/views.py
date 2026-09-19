from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User
from apps.users.serializers import RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    """
    Публичный эндпоинт для регистрации новых пользователей
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveAPIView):
    """
    Эндпоинт для получения профиля текущего аутентифицированного пользователя
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class BecomeLandlordView(APIView):
    """
    Эндпоинт для получения статуса арендодателя (landlord) текущим пользователем,
    обрабатывает POST запросы. Если у пользователя еще не установлен флаг `is_landlord`,
    переключает его в значение True, сохраняет в базе данных и возвращает обновленный профиль
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def post(self, request):
        if not request.user.is_landlord:
            request.user.is_landlord = True
            request.user.save(update_fields=['is_landlord'])
        return Response(UserSerializer(request.user).data)