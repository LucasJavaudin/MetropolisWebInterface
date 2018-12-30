import django_tables2 as tables

from .models import *

class CentroidTable(tables.Table):
    class Meta:
        model = Centroid
        fields = ['user_id', 'name', 'x', 'y']

class CrossingTable(tables.Table):
    class Meta:
        model = Crossing
        fields = ['user_id', 'name', 'x', 'y']

class LinkTable(tables.Table):
    class Meta:
        model = Link
        fields = ['user_id', 'name', 'origin', 'destination', 'lanes',
                  'length', 'speed', 'vdf', 'capacity']

class FunctionTable(tables.Table):
    class Meta:
        model = Function
        fields = ['user_id', 'name', 'expression']

class SimulationMOEsTable(tables.Table):
    class Meta:
        model = SimulationMOEs
        fields = ['day', 'stac', 'expect', 'users', 'drivers', 'tt0cost',
                  'toll', 'period', 'cong', 'vehkm', 'speed', 'narcs', 'ttime',
                  'cost', 'surp', 'equi', 'early', 'late', 'scost', 'earpop',
                  'ontpop', 'latpop']
        attrs = {'class': 'table table-bordered'}

class MatrixTable(tables.Table):
    class Meta:
        model = Matrix
        fields = ['p', 'q', 'r']

class PTMatrixTable(MatrixTable):
    """Table for public-transit travel times.
    
    The r variable needs to be renamed from Population to Travel time.
    """
    r = tables.Column(verbose_name='Travel time')

class TollTable(tables.Table):
    class Meta:
        model = Policy
        fields = ['location__link__user_id', 'baseValue']
