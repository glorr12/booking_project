from rest_framework import serializers

from apps.listings.models import Listing
from apps.users.models import AccountRole


class ListingSerializer(serializers.ModelSerializer):
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())
    owner_name = serializers.CharField(source='owner.name', read_only=True)

    class Meta:
        model = Listing
        fields = (
            'id', 'owner', 'owner_name', 'title', 'description', 'city', 'district',
            'price', 'rooms_count', 'housing_type', 'is_active', 'created_at',
        )
        read_only_fields = ('id', 'created_at')

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.user.role != AccountRole.LANDLORD:
            raise serializers.ValidationError('Only landlords can create/edit listings')
        return attrs