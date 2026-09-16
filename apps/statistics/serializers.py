from rest_framework import serializers

from apps.listings.serializers import ListingSerializer


class PopularListingSerializer(ListingSerializer):

    views_count = serializers.IntegerField(read_only=True)

    class Meta(ListingSerializer.Meta):
        fields = ListingSerializer.Meta.fields + ('views_count',)


class PopularSearchSerializer(serializers.Serializer):
    keyword = serializers.CharField()
    count = serializers.IntegerField()