from django.contrib.auth import password_validation
from rest_framework import serializers

from apps.users.models import User


class UserSerializer(serializers.ModelSerializer):
    """
    Сериализатор для представления данных учетной записи пользователя (только для чтения).
    Используется в эндпоинтах профиля для безопасной выдачи информации о клиенте или
    арендодателе без возможности изменения полей через этот класс
    """
    class Meta:
        model = User
        fields = ('id', 'email', 'name', 'role', 'is_landlord', 'created_at')
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    """
    Сериализатор для регистрации новых пользователей.
    Обеспечивает валидацию входящих данных, проверку надежности пароля
    и безопасное создание учетной записи через кастомный менеджер модели
    """
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'name', 'password', 'role', 'is_landlord')
        read_only_fields = ('id', 'is_landlord')

    def validate_password(self, value):
        """
        Проверяет сложность и надежность пароля по встроенным политикам безопасности Django
        """
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        """
        Создает нового пользователя с помощью кастомного менеджера модели
        """
        return User.objects.create_user(**validated_data)