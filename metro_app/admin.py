from django.contrib import admin

from .models import *

admin.site.register(Matrices)
admin.site.register(Network)
admin.site.register(FunctionSet)
admin.site.register(Function)
admin.site.register(Supply)
admin.site.register(Distribution)
admin.site.register(UserType)
admin.site.register(Demand)
admin.site.register(DemandSegment)
admin.site.register(Scenario)
admin.site.register(Centroid)
admin.site.register(Crossing)
admin.site.register(Link)
admin.site.register(LinkSelection)
admin.site.register(Path)
admin.site.register(Policy)
admin.site.register(Simulation)
admin.site.register(SimulationRun)
admin.site.register(Vector)
