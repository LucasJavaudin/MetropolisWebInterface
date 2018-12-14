import django_filters

from .models import *

def get_functions(request):
    # Retrieve the simulation from the request infos.
    simulation = Simulation.objects.get(
            pk=request.resolver_match.kwargs['simulation_id']
    )
    # Get the functions.
    functions = Function.objects.filter(
            functionset__supply__scenario__simulation=simulation
    )
    return functions

class CentroidFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    x_gt = django_filters.NumberFilter(field_name='x', lookup_expr='gt')
    x_lt = django_filters.NumberFilter(field_name='x', lookup_expr='lt')
    y_gt = django_filters.NumberFilter(field_name='y', lookup_expr='gt')
    y_lt = django_filters.NumberFilter(field_name='y', lookup_expr='lt')

    class Meta:
        model = Centroid
        fields = ['user_id', 'name', 'x', 'y']

class CrossingFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    x_gt = django_filters.NumberFilter(field_name='x', lookup_expr='gt')
    x_lt = django_filters.NumberFilter(field_name='x', lookup_expr='lt')
    y_gt = django_filters.NumberFilter(field_name='y', lookup_expr='gt')
    y_lt = django_filters.NumberFilter(field_name='y', lookup_expr='lt')

    class Meta:
        model = Crossing
        fields = ['user_id', 'name', 'x', 'y']

class LinkFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    lanes_gt = django_filters.NumberFilter(field_name='lanes', lookup_expr='gt')
    lanes_lt = django_filters.NumberFilter(field_name='lanes', lookup_expr='lt')
    length_gt = django_filters.NumberFilter(field_name='length', lookup_expr='gt')
    length_lt = django_filters.NumberFilter(field_name='length', lookup_expr='lt')
    speed_gt = django_filters.NumberFilter(field_name='speed', lookup_expr='gt')
    speed_lt = django_filters.NumberFilter(field_name='speed', lookup_expr='lt')
    vdf = django_filters.ModelChoiceFilter(queryset=get_functions)
    capacity_gt = django_filters.NumberFilter(field_name='capacity', lookup_expr='gt')
    capacity_lt = django_filters.NumberFilter(field_name='capacity', lookup_expr='lt')

    class Meta:
        model = Link
        fields = ['user_id', 'name', 'origin', 'destination', 'lanes', 'length', 'speed', 
                  'vdf', 'capacity']

class FunctionFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    expression = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Function
        fields = ['user_id', 'name', 'expression']

class SimulationMOEsFilter(django_filters.FilterSet):
    class Meta:
        model = SimulationMOEs
        exclude = ['id', 'simulation']

class MatrixFilter(django_filters.FilterSet):
    p = django_filters.CharFilter(lookup_expr='name__icontains')
    q = django_filters.CharFilter(lookup_expr='name__icontains')
    r_gt = django_filters.NumberFilter(field_name='r', lookup_expr='gt')
    r_lt = django_filters.NumberFilter(field_name='r', lookup_expr='lt')

    class Meta:
        model = Matrix
        fields = ['p', 'q', 'r']

class PTMatrixFilter(MatrixFilter):
    r = django_filters.NumberFilter(field_name='r', lookup_expr='exact',
                                    label='Travel time')
    r_gt = django_filters.NumberFilter(field_name='r', lookup_expr='gt',
                                       label='Travel time is greater than')
    r_lt = django_filters.NumberFilter(field_name='r', lookup_expr='lt',
                                       label='Travel time is less than')
