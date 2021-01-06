"""Implemented a External Script for the Batch Process on 20 December 2020 By Shubham"""

import os
import sys
import django
from django.utils import timezone

# Load the django website.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "metropolis_web_interface.settings")
django.setup()

from metro_app import models, functions, plots
from metro_app.views import NETWORK_THRESHOLD
TRAVELERS_THRESHOLD = 10000000  # 10 millions

print('Starting script...')

# Read argument of the script call.
try:
    batch_id = int(sys.argv[1])
except IndexError:
    raise SystemExit('MetroArgError: This script must be executed with the id '
                     + 'of the SimulationRun has an argument.')


try:
    batch = models.Batch.objects.get(pk=batch_id)
    batch.batchrun_set.all()
    simulation = batch.simulation

    for batch_run in batch.batchrun_set.all():
        if batch_run.centroid_file:
            functions.object_import_function(batch_run.centroid_file.file, simulation,  "centroid")

        if batch_run.crossing_file:
            functions.object_import_function( batch_run.crossing_file.file, simulation, "crossing")

        if batch_run.link_file:
            functions.object_import_function(batch_run.link_file.file, simulation, "link")

        if batch_run.public_transit_file:
            functions.public_transit_import_function(batch_run.public_transit_file.file, simulation)

        if batch_run.traveler_file:
            functions.traveler_zip_file(simulation, batch_run.traveler_file)

        if batch_run.pricing_file:
            functions.pricing_import_function(batch_run.pricing_file.file, simulation)

        if batch_run.function_file:
            functions.object_import_function(batch_run.function_file.file, simulation, "function")

        if batch_run.zip_file:
            functions.simulation_import(simulation, batch_run.zip_file)

        run = models.SimulationRun(name=batch_run.name, simulation=simulation)
        run.save()
        batch_run.run
        batch_run.save()
        functions.run_simulation(run, background=False)


except models.BatchRun.DoesNotExist:
    raise SystemExit('No BatchRun object corresponding'
                     + ' to the given id.')



batch.end_time = timezone.now
batch.status = "Finished"
batch.save()
