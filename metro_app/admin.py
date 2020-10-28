from django.contrib import admin

from metro_app import models

admin.site.register(models.Matrices)
admin.site.register(models.Network)
admin.site.register(models.FunctionSet)
admin.site.register(models.Function)
admin.site.register(models.Supply)
admin.site.register(models.Distribution)
admin.site.register(models.UserType)
admin.site.register(models.Demand)
admin.site.register(models.DemandSegment)
admin.site.register(models.Scenario)
admin.site.register(models.Centroid)
admin.site.register(models.Crossing)
admin.site.register(models.Link)
admin.site.register(models.LinkSelection)
admin.site.register(models.Path)
admin.site.register(models.Policy)
admin.site.register(models.Simulation)
admin.site.register(models.SimulationRun)
admin.site.register(models.Vector)

admin.site.register(models.Event)
admin.site.register(models.Article)
admin.site.register(models.ArticleFile)
admin.site.register(models.Environment)
