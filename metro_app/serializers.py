from rest_framework import serializers

from metro_app.models import *


class SimulationSerializer(serializers.HyperlinkedModelSerializer):
    api_endpoint = serializers.HyperlinkedIdentityField(
        view_name='metro:simulation_api_root',
        lookup_url_kwarg='simulation_id')
    user = serializers.StringRelatedField()
    environment = serializers.StringRelatedField()

    class Meta:
        model = Simulation
        fields = ['id', 'name', 'comment', 'user', 'public', 'pinned',
                  'environment', 'api_endpoint']


class CentroidSerializer(serializers.HyperlinkedModelSerializer):
    """Serializer for the Centroid object.

    The field id in the model corresponds to the field db_id in the serializer.
    The field user_id in the mode corresponds to the field id in the
    serializer.
    """
    id = serializers.SerializerMethodField('get_user_id')
    db_id = serializers.SerializerMethodField('get_db_id')

    class Meta:
        model = Centroid
        fields = ['id', 'name', 'x', 'y', 'db_id']

    def get_user_id(self, obj):
        return obj.user_id

    def get_db_id(self, obj):
        return obj.id
