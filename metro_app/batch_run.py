#Implemented a External Script for the Batch Process on 20 December 2020 By Shubham

import os
import sys
import json
from shutil import copyfile

import django
from django.utils import timezone
from django.conf import settings
from django.db.models import Sum

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
    run_id = int(sys.argv[1])
except IndexError:
    raise SystemExit('MetroArgError: This script must be executed with the id '
                     + 'of the SimulationRun has an argument.')


try:
    batch_id = int(sys.argv[1])
    batch = models.Batch.objects.get(pk=batch_id)
    batch.batchrun_set.all()
    sim = batch.simulation

    for batch_run in batch.batchrun_set.all():
        if batch_run.centroid_file:
            functions.object_import_function(batch_run.centroid_file.file, sim,  "centroid")

        if batch_run.crossing_file:
            functions.object_import_function( batch_run.crossing_file.file, sim, "crossing")

        if batch_run.link_file:
            functions.object_import_function(batch_run.link_file.file, sim, "link")

        if batch_run.pricing_file:
            functions.pricing_import_function(batch_run.pricing_file.file, sim)

        if batch_run.public_transit_file:
            functions.public_transit_import_function(batch_run.public_transit_file.file, sim)

        if batch_run.traveler_file:
            functions.traveler_zip_file(sim, batch_run.traveler_file)

        if batch_run.function_file:
            functions.object_import_function(batch_run.function_file.file, sim, "function")

        if batch_run.zip_file:
            functions.simulation_import(sim, batch_run.zip_file)

        run = models.SimulationRun(name=batch_run.name, simulation=sim)
        run.save()
        batch_run.run = run
        batch_run.save()
        functions.run_simulation(run, background=False)


except models.BatchRun.DoesNotExist:
    raise SystemExit('No BatchRun object corresponding'
                     + ' to the given id.')



batch.end_time = timezone.now
batch.status = "Finished"
