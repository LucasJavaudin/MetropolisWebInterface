import django_tables2 as tables

from metro_app import models


class CentroidTable(tables.Table):
    class Meta:
        model = models.Centroid
        fields = ['user_id', 'name', 'x', 'y']


class CrossingTable(tables.Table):
    class Meta:
        model = models.Crossing
        fields = ['user_id', 'name', 'x', 'y']


class LinkTable(tables.Table):
    class Meta:
        model = models.Link
        fields = ['user_id', 'name', 'origin', 'destination', 'lanes',
                  'length', 'speed', 'vdf', 'capacity']


class FunctionTable(tables.Table):
    class Meta:
        model = models.Function
        fields = ['user_id', 'name', 'expression']


class SimulationMOEsTable(tables.Table):
    class Meta:
        model = models.SimulationMOEs
        fields = ['day', 'stac', 'expect', 'users', 'drivers', 'tt0cost',
                  'toll', 'period', 'cong', 'vehkm', 'speed', 'narcs', 'ttime',
                  'cost', 'surp', 'equi', 'early', 'late', 'scost', 'earpop',
                  'ontpop', 'latpop']
        attrs = {'class': 'table table-bordered'}


class MatrixTable(tables.Table):
    class Meta:
        model = models.Matrix
        fields = ['p', 'q', 'r']


class PTMatrixTable(MatrixTable):
    """Table for public-transit travel times.

    The r variable needs to be renamed from Population to Travel time.
    """
    r = tables.Column(verbose_name='Travel time')


class TollTable(tables.Table):
    link_id = tables.Column(accessor='location.user_id')
    link_name = tables.Column(accessor='location.name')
    value_vector = tables.Column(accessor='get_value_vector',
                                 verbose_name='Value',
                                 order_by='baseValue')
    time_vector = tables.Column(accessor='get_time_vector',
                                verbose_name='Time',
                                orderable=False)
    user_type = tables.Column(accessor='usertype.name',
                              verbose_name='Traveler Type')

    class Meta:
        model = models.Policy
        fields = []
        sequence = ['link_id', 'link_name', 'value_vector', 'time_vector',
                    'user_type']
