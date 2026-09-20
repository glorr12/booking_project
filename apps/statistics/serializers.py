from rest_framework import serializers

from apps.listings.serializers import ListingSerializer


class PopularListingSerializer(ListingSerializer):
    """
    Сериализатор для вывода популярных листингов в расширенном формате.
    Наследуется от базового `ListingSerializer`, дополняя его динамически
    аннотированным полем количества просмотров
    """

    views_count = serializers.IntegerField(read_only=True)

    class Meta(ListingSerializer.Meta):
        fields = ListingSerializer.Meta.fields + ('views_count',)


class PopularSearchSerializer(serializers.Serializer):
    """
    Сериализатор для передачи данных о трендах и популярных поисковых запросах.
    Используется для сериализации агрегированной статистики по ключевым словам.
    """
    keyword = serializers.CharField()
    count = serializers.IntegerField()